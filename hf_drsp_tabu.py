#!/usr/bin/env python3
"""
HF-DRSP: Secuenciacion y ruteo de drones de entrega con flota heterogenea.

El script resuelve una instancia del problema con Busqueda Tabu:
- Flota heterogenea de drones con capacidad, autonomia y recarga.
- Misiones como rutas CD -> pedidos -> CD.
- Scheduling por dron con recarga entre misiones.
- Funcion objetivo penalizada para explorar soluciones infactibles.

Ejecutar:
    python3 hf_drsp_tabu.py
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
import random
from typing import Dict, Iterable, List, Optional, Tuple


DEPOT = 0


@dataclass(frozen=True)
class Customer:
    id: int
    x: float
    y: float
    demand: float


@dataclass(frozen=True)
class Drone:
    id: int
    capacity: float
    battery: float
    recharge: float


@dataclass
class MissionEval:
    distance: float
    load: float
    capacity_excess: float
    battery_excess: float
    start: float
    finish: float


Solution = List[List[List[int]]]
Move = Tuple[str, Tuple[int, ...], List[Tuple[int, int]]]


def euclidean(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def build_distance_matrix(customers: Dict[int, Customer]) -> Dict[Tuple[int, int], float]:
    points = {DEPOT: (0.0, 0.0)}
    points.update({cid: (c.x, c.y) for cid, c in customers.items()})
    return {
        (i, j): euclidean(points[i], points[j])
        for i in points
        for j in points
    }


def route_distance(route: List[int], distances: Dict[Tuple[int, int], float]) -> float:
    if not route:
        return 0.0
    total = distances[(DEPOT, route[0])]
    for previous, current in zip(route, route[1:]):
        total += distances[(previous, current)]
    total += distances[(route[-1], DEPOT)]
    return total


def evaluate_solution(
    solution: Solution,
    drones: List[Drone],
    customers: Dict[int, Customer],
    distances: Dict[Tuple[int, int], float],
    alpha: float,
    beta: float,
) -> Tuple[float, float, float, float, List[List[MissionEval]]]:
    makespan = 0.0
    capacity_excess = 0.0
    battery_excess = 0.0
    schedule: List[List[MissionEval]] = []

    for drone_idx, missions in enumerate(solution):
        drone = drones[drone_idx]
        clock = 0.0
        drone_schedule: List[MissionEval] = []

        for mission_idx, mission in enumerate(missions):
            distance = route_distance(mission, distances)
            load = sum(customers[customer_id].demand for customer_id in mission)
            c_excess = max(0.0, load - drone.capacity)
            b_excess = max(0.0, distance - drone.battery)

            start = clock
            finish = start + distance
            drone_schedule.append(
                MissionEval(
                    distance=distance,
                    load=load,
                    capacity_excess=c_excess,
                    battery_excess=b_excess,
                    start=start,
                    finish=finish,
                )
            )

            capacity_excess += c_excess
            battery_excess += b_excess
            clock = finish
            if mission_idx < len(missions) - 1:
                clock += drone.recharge

        makespan = max(makespan, clock)
        schedule.append(drone_schedule)

    objective = makespan + alpha * capacity_excess + beta * battery_excess
    return objective, makespan, capacity_excess, battery_excess, schedule


def is_feasible(
    solution: Solution,
    drones: List[Drone],
    customers: Dict[int, Customer],
    distances: Dict[Tuple[int, int], float],
) -> bool:
    _, _, capacity_excess, battery_excess, _ = evaluate_solution(
        solution, drones, customers, distances, alpha=1.0, beta=1.0
    )
    return capacity_excess == 0.0 and battery_excess == 0.0


def validate_customer_coverage(solution: Solution, customer_ids: Iterable[int]) -> None:
    expected = sorted(customer_ids)
    assigned = sorted(
        customer_id
        for drone_missions in solution
        for mission in drone_missions
        for customer_id in mission
    )
    if assigned != expected:
        missing = sorted(set(expected) - set(assigned))
        duplicated = sorted({cid for cid in assigned if assigned.count(cid) > 1})
        raise ValueError(
            "Solucion invalida: "
            f"pedidos faltantes={missing}, pedidos duplicados={duplicated}"
        )


def normalize_solution(solution: Solution) -> Solution:
    return [[mission for mission in drone_missions if mission] for drone_missions in solution]


def initial_solution(
    drones: List[Drone],
    customers: Dict[int, Customer],
    distances: Dict[Tuple[int, int], float],
) -> Solution:
    """Construye una solucion inicial greedy por insercion secuencial."""
    solution: Solution = [[] for _ in drones]
    ordered_customers = sorted(customers.values(), key=lambda c: c.demand, reverse=True)
    drone_order = sorted(range(len(drones)), key=lambda idx: drones[idx].capacity, reverse=True)

    for customer in ordered_customers:
        inserted = False
        for drone_idx in drone_order:
            drone = drones[drone_idx]
            for mission in solution[drone_idx]:
                candidate = mission + [customer.id]
                if (
                    sum(customers[cid].demand for cid in candidate) <= drone.capacity
                    and route_distance(candidate, distances) <= drone.battery
                ):
                    mission.append(customer.id)
                    inserted = True
                    break
            if inserted:
                break

        if not inserted:
            best_drone = min(
                range(len(drones)),
                key=lambda idx: max(0.0, customers[customer.id].demand - drones[idx].capacity)
                + max(0.0, route_distance([customer.id], distances) - drones[idx].battery),
            )
            solution[best_drone].append([customer.id])

    return normalize_solution(solution)


def mission_positions(solution: Solution) -> List[Tuple[int, int, int]]:
    positions = []
    for drone_idx, missions in enumerate(solution):
        for mission_idx, mission in enumerate(missions):
            for pos_idx, _ in enumerate(mission):
                positions.append((drone_idx, mission_idx, pos_idx))
    return positions


def random_existing_or_new_mission(
    solution: Solution,
    drone_idx: int,
    rng: random.Random,
    allow_new: bool = True,
) -> int:
    mission_count = len(solution[drone_idx])
    if allow_new and (mission_count == 0 or rng.random() < 0.25):
        return mission_count
    return rng.randrange(mission_count)


def generate_shift(solution: Solution, rng: random.Random) -> Optional[Tuple[Solution, Move]]:
    positions = mission_positions(solution)
    if not positions:
        return None

    new_solution = deepcopy(solution)
    from_drone, from_mission, from_pos = rng.choice(positions)
    customer_id = new_solution[from_drone][from_mission].pop(from_pos)
    old_drone = from_drone

    if not new_solution[from_drone][from_mission]:
        del new_solution[from_drone][from_mission]

    to_drone = rng.randrange(len(new_solution))
    to_mission = random_existing_or_new_mission(new_solution, to_drone, rng, allow_new=True)

    if to_mission == len(new_solution[to_drone]):
        new_solution[to_drone].append([customer_id])
    else:
        insert_pos = rng.randrange(len(new_solution[to_drone][to_mission]) + 1)
        new_solution[to_drone][to_mission].insert(insert_pos, customer_id)

    if new_solution == solution:
        return None

    tabu_attributes = [(customer_id, old_drone)]
    move: Move = ("shift", (customer_id, old_drone, to_drone), tabu_attributes)
    return normalize_solution(new_solution), move


def generate_swap(solution: Solution, rng: random.Random) -> Optional[Tuple[Solution, Move]]:
    positions = mission_positions(solution)
    if len(positions) < 2:
        return None

    a, b = rng.sample(positions, 2)
    if a[:2] == b[:2] and a[2] == b[2]:
        return None

    new_solution = deepcopy(solution)
    d1, m1, p1 = a
    d2, m2, p2 = b
    c1 = new_solution[d1][m1][p1]
    c2 = new_solution[d2][m2][p2]
    new_solution[d1][m1][p1], new_solution[d2][m2][p2] = c2, c1

    if new_solution == solution:
        return None

    tabu_attributes = [(c1, d1), (c2, d2)]
    move: Move = ("swap", (c1, d1, c2, d2), tabu_attributes)
    return normalize_solution(new_solution), move


def generate_neighbors(
    solution: Solution,
    rng: random.Random,
    neighborhood_size: int,
) -> Iterable[Tuple[Solution, Move]]:
    seen = set()
    attempts = 0
    max_attempts = neighborhood_size * 8

    while len(seen) < neighborhood_size and attempts < max_attempts:
        attempts += 1
        generator = generate_shift if rng.random() < 0.65 else generate_swap
        generated = generator(solution, rng)
        if generated is None:
            continue

        neighbor, move = generated
        signature = repr(neighbor)
        if signature in seen:
            continue
        seen.add(signature)
        yield neighbor, move


def tabu_search(
    drones: List[Drone],
    customers: Dict[int, Customer],
    distances: Dict[Tuple[int, int], float],
    max_iterations: int = 2000,
    max_no_improvement: int = 300,
    tabu_min: int = 7,
    tabu_max: int = 15,
    neighborhood_size: int = 90,
    seed: int = 42,
) -> Dict[str, object]:
    rng = random.Random(seed)
    alpha = 25.0
    beta = 8.0

    current = initial_solution(drones, customers, distances)
    current_eval = evaluate_solution(current, drones, customers, distances, alpha, beta)

    best = deepcopy(current)
    best_eval = current_eval
    best_feasible = deepcopy(current) if is_feasible(current, drones, customers, distances) else None
    best_feasible_eval = current_eval if best_feasible is not None else None

    tabu_until: Dict[Tuple[int, int], int] = {}
    no_improvement = 0
    history = []

    for iteration in range(1, max_iterations + 1):
        best_candidate = None
        best_candidate_eval = None
        best_candidate_move = None

        for candidate, move in generate_neighbors(current, rng, neighborhood_size):
            objective, makespan, capacity_excess, battery_excess, _ = evaluate_solution(
                candidate, drones, customers, distances, alpha, beta
            )
            tabu_attributes = move[2]
            is_tabu = any(tabu_until.get(attr, -1) >= iteration for attr in tabu_attributes)

            aspiration = (
                best_feasible_eval is not None
                and capacity_excess == 0.0
                and battery_excess == 0.0
                and makespan < best_feasible_eval[1]
            )
            if is_tabu and not aspiration:
                continue

            if best_candidate_eval is None or objective < best_candidate_eval[0]:
                best_candidate = candidate
                best_candidate_eval = (objective, makespan, capacity_excess, battery_excess, None)
                best_candidate_move = move

        if best_candidate is None or best_candidate_eval is None or best_candidate_move is None:
            break

        current = best_candidate
        current_eval = evaluate_solution(current, drones, customers, distances, alpha, beta)
        _, makespan, capacity_excess, battery_excess, _ = current_eval

        for attr in best_candidate_move[2]:
            tabu_until[attr] = iteration + rng.randint(tabu_min, tabu_max)

        if capacity_excess == 0.0 and battery_excess == 0.0:
            alpha = max(5.0, alpha * 0.97)
            beta = max(2.0, beta * 0.97)
        else:
            alpha = min(500.0, alpha * (1.03 if capacity_excess > 0.0 else 0.99))
            beta = min(500.0, beta * (1.03 if battery_excess > 0.0 else 0.99))

        improved = False
        if current_eval[0] < best_eval[0]:
            best = deepcopy(current)
            best_eval = current_eval
            improved = True

        if capacity_excess == 0.0 and battery_excess == 0.0:
            if best_feasible_eval is None or makespan < best_feasible_eval[1]:
                best_feasible = deepcopy(current)
                best_feasible_eval = current_eval
                improved = True

        no_improvement = 0 if improved else no_improvement + 1
        history.append((iteration, best_eval[0], best_eval[1], alpha, beta))

        if no_improvement >= max_no_improvement:
            break

    selected = best_feasible if best_feasible is not None else best
    selected_eval = best_feasible_eval if best_feasible_eval is not None else best_eval
    validate_customer_coverage(selected, customers.keys())
    final_eval = evaluate_solution(selected, drones, customers, distances, alpha, beta)

    return {
        "solution": selected,
        "objective": final_eval[0],
        "makespan": final_eval[1],
        "capacity_excess": final_eval[2],
        "battery_excess": final_eval[3],
        "schedule": final_eval[4],
        "iterations": history[-1][0] if history else 0,
        "alpha": alpha,
        "beta": beta,
        "history": history,
    }


def demo_instance() -> Tuple[List[Drone], Dict[int, Customer], Dict[Tuple[int, int], float]]:
    customers = {
        1: Customer(1, 2, 6, 1.4),
        2: Customer(2, 5, 3, 2.0),
        3: Customer(3, 1, 8, 1.2),
        4: Customer(4, 7, 6, 2.8),
        5: Customer(5, 8, 2, 2.3),
        6: Customer(6, 3, 9, 1.5),
        7: Customer(7, 6, 9, 2.1),
        8: Customer(8, 9, 7, 1.8),
        9: Customer(9, 4, 1, 1.0),
        10: Customer(10, 10, 4, 2.7),
        11: Customer(11, 12, 8, 1.6),
        12: Customer(12, 11, 2, 2.4),
        13: Customer(13, 13, 5, 1.9),
        14: Customer(14, 6, 12, 1.1),
        15: Customer(15, 2, 11, 2.2),
    }

    drones = [
        Drone(id=1, capacity=5.0, battery=25.0, recharge=4.0),
        Drone(id=2, capacity=4.0, battery=20.0, recharge=3.0),
        Drone(id=3, capacity=7.0, battery=32.0, recharge=6.0),
        Drone(id=4, capacity=3.5, battery=17.0, recharge=2.0),
    ]

    distances = build_distance_matrix(customers)
    return drones, customers, distances


def print_instance(drones: List[Drone], customers: Dict[int, Customer]) -> None:
    print("=== Instancia HF-DRSP ===")
    print("Centro de distribucion: (0, 0)")
    print("\nDrones:")
    for drone in drones:
        print(
            f"  Dron {drone.id}: Q={drone.capacity:.1f}, "
            f"B={drone.battery:.1f}, R={drone.recharge:.1f}"
        )
    print("\nPedidos:")
    for customer in customers.values():
        print(
            f"  Pedido {customer.id:02d}: "
            f"coord=({customer.x:.1f}, {customer.y:.1f}), peso={customer.demand:.1f}"
        )


def print_solution(result: Dict[str, object], drones: List[Drone]) -> None:
    solution = result["solution"]
    schedule = result["schedule"]
    assert isinstance(solution, list)
    assert isinstance(schedule, list)

    print("\n=== Resultado Busqueda Tabu ===")
    print(f"Iteraciones ejecutadas: {result['iterations']}")
    print(f"Makespan Cmax: {result['makespan']:.2f}")
    print(f"Funcion objetivo penalizada: {result['objective']:.2f}")
    print(f"Exceso total capacidad: {result['capacity_excess']:.2f}")
    print(f"Exceso total bateria: {result['battery_excess']:.2f}")
    print(f"Alpha final: {result['alpha']:.2f} | Beta final: {result['beta']:.2f}")

    print("\nPlan por dron:")
    for drone_idx, missions in enumerate(solution):
        drone = drones[drone_idx]
        print(f"\nDron {drone.id}:")
        if not missions:
            print("  Sin misiones asignadas.")
            continue

        for mission_idx, mission in enumerate(missions):
            info = schedule[drone_idx][mission_idx]
            feasibility = "FACTIBLE"
            if info.capacity_excess > 0 or info.battery_excess > 0:
                feasibility = "INF. PENALIZADA"

            print(
                f"  Mision {mission_idx + 1}: {mission} | "
                f"inicio={info.start:.2f}, fin={info.finish:.2f}, "
                f"dist={info.distance:.2f}, carga={info.load:.2f}, {feasibility}"
            )
            if mission_idx < len(missions) - 1:
                print(f"    Recarga: {drone.recharge:.2f}")


def main() -> None:
    drones, customers, distances = demo_instance()
    print_instance(drones, customers)
    result = tabu_search(
        drones,
        customers,
        distances,
        max_iterations=2000,
        max_no_improvement=300,
        tabu_min=7,
        tabu_max=15,
        neighborhood_size=100,
        seed=2026,
    )
    print_solution(result, drones)


if __name__ == "__main__":
    main()
