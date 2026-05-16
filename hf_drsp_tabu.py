#!/usr/bin/env python3
"""
HF-DRSP: Secuenciacion y ruteo de drones de entrega con flota heterogenea.

El script resuelve una instancia del problema con Busqueda Tabu. El modelo
combina dos componentes:
- Flota heterogenea de drones con capacidad, autonomia y recarga.
- Misiones como rutas CD -> pedidos -> CD.
- Scheduling por dron con recarga entre misiones.
- Funcion objetivo penalizada para explorar soluciones infactibles.

Esquema teorico de la Busqueda Tabu implementada:
1. Definir una codificacion de solucion S.
2. Construir una solucion inicial S0.
3. Evaluar S mediante una funcion objetivo penalizada F(S).
4. Generar un vecindario N(S) con movimientos de insercion y de intercambio.
5. Seleccionar el mejor vecino admisible, respetando la lista tabu.
6. Aplicar criterio de aspiracion si un movimiento tabu mejora el mejor historico.
7. Actualizar la memoria tabu, la solucion actual y la mejor solucion conocida.
8. Ajustar penalizaciones dinamicas para balancear factibilidad y exploracion.
9. Detener por maximo de iteraciones o por iteraciones sin mejora.

Ejecutar:
    python3 hf_drsp_tabu.py
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
import random
from typing import Dict, Iterable, List, Optional, Tuple


# El centro de distribucion se modela como nodo 0. Los clientes usan IDs 1..N.
DEPOT = 0


@dataclass(frozen=True)
class Customer:
    """Pedido/cliente de la instancia.

    Atributos:
        id: Identificador del pedido.
        x, y: Coordenadas cartesianas del cliente.
        demand: Peso del pedido.
    """

    id: int
    x: float
    y: float
    demand: float


@dataclass(frozen=True)
class Drone:
    """Dron de la flota heterogenea.

    Atributos:
        id: Identificador del dron.
        capacity: Capacidad maxima Q_k.
        battery: Autonomia maxima B_k, medida como distancia maxima.
        recharge: Tiempo de recarga R_k entre misiones consecutivas.
    """

    id: int
    capacity: float
    battery: float
    recharge: float


@dataclass
class MissionEval:
    """Resultado de evaluar una mision especifica.

    Esta estructura almacena tanto valores de ruteo, como distancia y carga,
    como valores de scheduling, como instante de inicio y finalizacion.
    """

    distance: float
    load: float
    capacity_excess: float
    battery_excess: float
    start: float
    finish: float


# Codificacion de solucion:
# Solution[dron][mision][posicion] = ID del pedido visitado.
# Ejemplo: [[[8], [12]], [[6], [2, 1]]] representa dos drones.
Solution = List[List[List[int]]]

# Codificacion de movimiento:
# (tipo_movimiento, detalle, atributos_tabu)
# atributos_tabu usa pares (ID_Pedido, ID_Dron) para evitar reversas inmediatas.
Move = Tuple[str, Tuple[int, ...], List[Tuple[int, int]]]


def euclidean(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Calcula distancia euclidiana entre dos puntos."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def build_distance_matrix(customers: Dict[int, Customer]) -> Dict[Tuple[int, int], float]:
    """Construye la matriz completa de distancias entre CD y clientes."""
    points = {DEPOT: (0.0, 0.0)}
    points.update({cid: (c.x, c.y) for cid, c in customers.items()})
    return {
        (i, j): euclidean(points[i], points[j])
        for i in points
        for j in points
    }


def route_distance(route: List[int], distances: Dict[Tuple[int, int], float]) -> float:
    """Calcula la distancia de una ruta cerrada CD -> clientes -> CD."""
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
    """Evalua una solucion segun la funcion objetivo penalizada.

    Paso teorico de Busqueda Tabu: evaluacion de la solucion.

    Para cada dron se simula cronologicamente su secuencia de misiones:
    - El tiempo de vuelo de una mision se aproxima por la distancia de la ruta.
    - Entre dos misiones consecutivas se agrega el tiempo de recarga R_k.
    - El makespan Cmax es el mayor tiempo de finalizacion entre drones.

    La funcion penalizada permite aceptar temporalmente soluciones infactibles:
        F(S) = Cmax + alpha * exceso_capacidad + beta * exceso_bateria

    Retorna:
        objective: Valor F(S).
        makespan: Cmax sin penalizaciones.
        capacity_excess: Suma de excesos sobre Q_k.
        battery_excess: Suma de excesos sobre B_k.
        schedule: Detalle temporal y operativo de cada mision.
    """
    makespan = 0.0
    capacity_excess = 0.0
    battery_excess = 0.0
    schedule: List[List[MissionEval]] = []

    for drone_idx, missions in enumerate(solution):
        drone = drones[drone_idx]
        clock = 0.0
        drone_schedule: List[MissionEval] = []

        for mission_idx, mission in enumerate(missions):
            # Evaluacion de ruteo: distancia total y carga transportada.
            distance = route_distance(mission, distances)
            load = sum(customers[customer_id].demand for customer_id in mission)
            c_excess = max(0.0, load - drone.capacity)
            b_excess = max(0.0, distance - drone.battery)

            # Evaluacion de scheduling: inicio, finalizacion y recarga posterior.
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
    """Indica si una solucion respeta capacidad y autonomia."""
    _, _, capacity_excess, battery_excess, _ = evaluate_solution(
        solution, drones, customers, distances, alpha=1.0, beta=1.0
    )
    return capacity_excess == 0.0 and battery_excess == 0.0


def validate_customer_coverage(solution: Solution, customer_ids: Iterable[int]) -> None:
    """Verifica que cada pedido sea atendido exactamente una vez."""
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
    """Elimina misiones vacias despues de aplicar movimientos de vecindario."""
    return [[mission for mission in drone_missions if mission] for drone_missions in solution]


def initial_solution(
    drones: List[Drone],
    customers: Dict[int, Customer],
    distances: Dict[Tuple[int, int], float],
) -> Solution:
    """Construye la solucion inicial S0.

    Paso teorico de Busqueda Tabu: inicializacion.

    Se usa una heuristica greedy:
    1. Ordena pedidos por demanda descendente.
    2. Intenta insertar cada pedido en misiones existentes de drones con mayor
       capacidad.
    3. Si no encuentra insercion factible, crea una mision nueva en el dron
       con menor violacion estimada.

    La solucion inicial no tiene que ser optima; su funcion es dar un punto de
    partida razonable para explorar el espacio de soluciones.
    """
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
    """Lista todas las posiciones donde existe un pedido dentro de la solucion."""
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
    """Elige una mision destino existente o una nueva mision."""
    mission_count = len(solution[drone_idx])
    if allow_new and (mission_count == 0 or rng.random() < 0.25):
        return mission_count
    return rng.randrange(mission_count)


def generate_shift(solution: Solution, rng: random.Random) -> Optional[Tuple[Solution, Move]]:
    """Genera un vecino mediante movimiento Shift.

    Paso teorico de Busqueda Tabu: construccion del vecindario N(S).

    Movimiento Shift:
    - Selecciona un pedido de una mision origen.
    - Lo remueve de su posicion actual.
    - Lo inserta en una mision existente o en una mision nueva.

    El atributo tabu registrado es (pedido, dron_origen), lo que prohibe
    devolver inmediatamente ese pedido al dron del que salio.
    """
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
    """Genera un vecino mediante movimiento Swap.

    Paso teorico de Busqueda Tabu: construccion del vecindario N(S).

    Movimiento Swap:
    - Selecciona dos pedidos ubicados en la solucion.
    - Intercambia sus posiciones.

    Este movimiento ayuda a balancear carga, distancia y tiempos entre drones.
    Los atributos tabu prohiben revertir de inmediato el intercambio.
    """
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
    """Genera una muestra aleatoria del vecindario N(S).

    En problemas combinatorios grandes, evaluar todos los vecinos puede ser
    costoso. Por eso se genera una muestra de tamano `neighborhood_size`.
    La mezcla 65% Shift y 35% Swap favorece la reasignacion de pedidos, pero
    conserva intercambios para intensificar la busqueda alrededor de buenas
    estructuras.
    """
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
    """Ejecuta el algoritmo principal de Busqueda Tabu.

    Pasos teoricos implementados:
    1. Inicializacion:
       - Fijar semilla aleatoria.
       - Definir penalizaciones iniciales alpha y beta.
       - Construir solucion inicial S0.

    2. Evaluacion:
       - Calcular F(S), Cmax y excesos de restricciones.

    3. Memoria tabu:
       - Guardar atributos (ID_Pedido, ID_Dron) con una iteracion de expiracion.
       - Usar tenor tabu dinamico aleatorio entre `tabu_min` y `tabu_max`.

    4. Generacion de vecindario:
       - Crear vecinos por Shift y Swap.

    5. Seleccion de movimiento:
       - Escoger el mejor vecino admisible segun F(S).
       - Rechazar movimientos tabu salvo que cumplan aspiracion.

    6. Aspiracion:
       - Si un movimiento tabu produce un makespan factible estrictamente mejor
         que el mejor historico factible, se acepta.

    7. Actualizacion:
       - Mover la solucion actual al mejor vecino seleccionado.
       - Actualizar lista tabu, mejor solucion global y mejor factible.
       - Ajustar alpha y beta segun la presencia de violaciones.

    8. Parada:
       - Terminar al alcanzar `max_iterations`.
       - O terminar tras `max_no_improvement` iteraciones consecutivas sin mejora.
    """
    rng = random.Random(seed)
    alpha = 25.0
    beta = 8.0

    # Paso 1: construir solucion inicial y evaluarla.
    current = initial_solution(drones, customers, distances)
    current_eval = evaluate_solution(current, drones, customers, distances, alpha, beta)

    # Mejor solucion segun la funcion penalizada y mejor solucion factible.
    best = deepcopy(current)
    best_eval = current_eval
    best_feasible = deepcopy(current) if is_feasible(current, drones, customers, distances) else None
    best_feasible_eval = current_eval if best_feasible is not None else None

    # Memoria tabu: atributo -> iteracion hasta la que permanece prohibido.
    tabu_until: Dict[Tuple[int, int], int] = {}
    no_improvement = 0
    history = []

    for iteration in range(1, max_iterations + 1):
        best_candidate = None
        best_candidate_eval = None
        best_candidate_move = None

        # Paso 2: generar y evaluar una muestra del vecindario N(current).
        for candidate, move in generate_neighbors(current, rng, neighborhood_size):
            objective, makespan, capacity_excess, battery_excess, _ = evaluate_solution(
                candidate, drones, customers, distances, alpha, beta
            )
            tabu_attributes = move[2]

            # Paso 3: verificar si algun atributo del movimiento esta tabu.
            is_tabu = any(tabu_until.get(attr, -1) >= iteration for attr in tabu_attributes)

            # Paso 4: criterio de aspiracion global.
            # Un movimiento tabu puede aceptarse si mejora el mejor Cmax factible.
            aspiration = (
                best_feasible_eval is not None
                and capacity_excess == 0.0
                and battery_excess == 0.0
                and makespan < best_feasible_eval[1]
            )
            if is_tabu and not aspiration:
                continue

            # Paso 5: elegir el mejor vecino admisible segun F(S).
            if best_candidate_eval is None or objective < best_candidate_eval[0]:
                best_candidate = candidate
                best_candidate_eval = (objective, makespan, capacity_excess, battery_excess, None)
                best_candidate_move = move

        # Si no existe vecino admisible, se detiene la busqueda.
        if best_candidate is None or best_candidate_eval is None or best_candidate_move is None:
            break

        # Paso 6: mover la solucion actual al mejor vecino seleccionado.
        current = best_candidate
        current_eval = evaluate_solution(current, drones, customers, distances, alpha, beta)
        _, makespan, capacity_excess, battery_excess, _ = current_eval

        # Paso 7: actualizar memoria tabu con tenor dinamico aleatorio.
        for attr in best_candidate_move[2]:
            tabu_until[attr] = iteration + rng.randint(tabu_min, tabu_max)

        # Paso 8: actualizar penalizaciones dinamicas.
        # Si la solucion actual es factible, se relaja la penalizacion.
        # Si hay violaciones, se incrementa el castigo correspondiente.
        if capacity_excess == 0.0 and battery_excess == 0.0:
            alpha = max(5.0, alpha * 0.97)
            beta = max(2.0, beta * 0.97)
        else:
            alpha = min(500.0, alpha * (1.03 if capacity_excess > 0.0 else 0.99))
            beta = min(500.0, beta * (1.03 if battery_excess > 0.0 else 0.99))

        # Paso 9: actualizar mejores soluciones historicas.
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
        best_feasible_makespan = best_feasible_eval[1] if best_feasible_eval is not None else None
        history.append((iteration, best_eval[0], best_eval[1], alpha, beta, best_feasible_makespan))

        # Paso 10: criterio de parada por estancamiento.
        if no_improvement >= max_no_improvement:
            break

    # Se reporta preferentemente la mejor solucion factible. Si no existiera,
    # se reportaria la mejor solucion penalizada encontrada.
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
    """Define la instancia academica usada en el taller.

    Clientes:
        Cada entrada contiene ID, coordenada x, coordenada y y peso del pedido.

    Drones:
        Cada entrada contiene ID, capacidad Q_k, autonomia B_k y recarga R_k.
    """
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
    """Imprime los datos base de la instancia."""
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
    """Imprime la solucion en formato legible para analisis academico."""
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
    """Punto de entrada del script."""
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
