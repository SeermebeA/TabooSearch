#!/usr/bin/env python3
"""
Job Shop Scheduling Problem (JSSP) resuelto con Busqueda Tabu.

Enunciado:
    Un taller de manufactura debe procesar n trabajos en m maquinas. Cada
    trabajo tiene una ruta tecnologica propia, compuesta por operaciones que
    deben ejecutarse en un orden fijo. Cada operacion requiere una maquina
    especifica y tiene un tiempo de procesamiento determinista. Una maquina
    solo puede procesar una operacion a la vez y no se permite interrupcion
    una vez iniciada una operacion.

Objetivo:
    Minimizar el makespan Cmax, es decir, el tiempo en que finaliza la ultima
    operacion del ultimo trabajo.

Esquema de Busqueda Tabu:
1. Codificar una solucion como prioridades de trabajos por maquina.
2. Decodificar esas prioridades en un calendario factible.
3. Evaluar el calendario mediante Cmax.
4. Generar vecinos intercambiando prioridades en una maquina.
5. Usar una lista tabu para evitar reversas inmediatas.
6. Aplicar aspiracion si un movimiento tabu mejora el mejor Cmax historico.
7. Detener por maximo de iteraciones o por iteraciones sin mejora.

Ejecutar:
    python3 jssp_tabu.py
"""

from __future__ import annotations

from dataclasses import dataclass
import heapq
import random
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class Operation:
    """Operacion de un trabajo.

    Atributos:
        job_id: Identificador del trabajo.
        op_id: Posicion de la operacion dentro de la ruta del trabajo.
        machine_id: Maquina requerida.
        processing_time: Tiempo de procesamiento determinista.
    """

    job_id: int
    op_id: int
    machine_id: int
    processing_time: int


@dataclass
class ScheduledOperation:
    """Operacion ya programada en el calendario."""

    job_id: int
    op_id: int
    machine_id: int
    processing_time: int
    start: int
    finish: int


# Instancia JSSP: jobs[job_id] = ruta tecnologica del trabajo.
Jobs = Dict[int, List[Operation]]

# Solucion: machine_sequences[machine_id] = orden de prioridad de trabajos.
# Cada trabajo aparece una vez por cada operacion que requiere esa maquina.
MachineSequences = Dict[int, List[int]]

# Movimiento: intercambiar dos posiciones en la secuencia de una maquina.
Move = Tuple[int, int, int, int, int]


def demo_instance() -> Tuple[Jobs, List[int]]:
    """Define una instancia academica pequena de JSSP.

    La instancia contiene 5 trabajos y 4 maquinas. Cada trabajo tiene una ruta
    tecnologica diferente, lo que distingue el JSSP de un Flow-Shop.
    """
    raw_jobs = {
        1: [(1, 6), (2, 4), (3, 5), (4, 3)],
        2: [(3, 5), (1, 3), (4, 6), (2, 4)],
        3: [(2, 4), (4, 7), (1, 5), (3, 3)],
        4: [(4, 3), (3, 6), (2, 5), (1, 4)],
        5: [(1, 5), (3, 4), (2, 6), (4, 5)],
    }

    jobs: Jobs = {}
    for job_id, route in raw_jobs.items():
        jobs[job_id] = [
            Operation(
                job_id=job_id,
                op_id=op_idx,
                machine_id=machine_id,
                processing_time=processing_time,
            )
            for op_idx, (machine_id, processing_time) in enumerate(route)
        ]

    machines = sorted({machine_id for route in raw_jobs.values() for machine_id, _ in route})
    return jobs, machines


def build_initial_solution(jobs: Jobs, machines: List[int]) -> MachineSequences:
    """Construye una solucion inicial por orden natural de trabajos.

    Para cada maquina se crea una lista con los trabajos que requieren esa
    maquina. Si un trabajo visita una maquina mas de una vez, apareceria mas de
    una vez en la lista.
    """
    sequences: MachineSequences = {machine_id: [] for machine_id in machines}
    for job_id in sorted(jobs):
        for operation in jobs[job_id]:
            sequences[operation.machine_id].append(job_id)
    return sequences


def decode_schedule(
    jobs: Jobs,
    machines: List[int],
    machine_sequences: MachineSequences,
) -> Tuple[int, List[ScheduledOperation]]:
    """Decodifica prioridades de maquina en un calendario factible.

    El decodificador implementa una simulacion de lista:
    - Cada trabajo solo puede liberar su siguiente operacion cuando la anterior
      ya fue programada.
    - Cada maquina procesa operaciones segun la secuencia de prioridad dada.
    - En cada paso se agenda la operacion disponible con menor inicio posible.

    Este procedimiento conserva las dos restricciones principales del JSSP:
    precedencia tecnologica por trabajo y capacidad unitaria por maquina.
    """
    machine_available = {machine_id: 0 for machine_id in machines}
    job_available = {job_id: 0 for job_id in jobs}
    next_op_idx = {job_id: 0 for job_id in jobs}
    machine_pointer = {machine_id: 0 for machine_id in machines}
    total_operations = sum(len(route) for route in jobs.values())
    scheduled: List[ScheduledOperation] = []

    # Cola de eventos: (inicio_posible, maquina, trabajo, op_id).
    ready_heap: List[Tuple[int, int, int, int]] = []

    def push_ready_operations() -> None:
        """Agrega operaciones que estan listas segun las prioridades actuales."""
        for machine_id in machines:
            sequence = machine_sequences[machine_id]
            pointer = machine_pointer[machine_id]
            if pointer >= len(sequence):
                continue

            job_id = sequence[pointer]
            op_idx = next_op_idx[job_id]
            if op_idx >= len(jobs[job_id]):
                continue

            operation = jobs[job_id][op_idx]
            if operation.machine_id != machine_id:
                continue

            earliest_start = max(machine_available[machine_id], job_available[job_id])
            item = (earliest_start, machine_id, job_id, operation.op_id)
            if item not in ready_heap:
                heapq.heappush(ready_heap, item)

    push_ready_operations()

    while len(scheduled) < total_operations:
        if not ready_heap:
            raise ValueError(
                "No hay operaciones disponibles. La secuencia de maquinas no "
                "puede decodificarse en un calendario factible."
            )

        earliest_start, machine_id, job_id, op_id = heapq.heappop(ready_heap)
        operation = jobs[job_id][next_op_idx[job_id]]

        if operation.op_id != op_id or operation.machine_id != machine_id:
            continue

        start = max(earliest_start, machine_available[machine_id], job_available[job_id])
        finish = start + operation.processing_time

        scheduled.append(
            ScheduledOperation(
                job_id=job_id,
                op_id=operation.op_id,
                machine_id=machine_id,
                processing_time=operation.processing_time,
                start=start,
                finish=finish,
            )
        )

        machine_available[machine_id] = finish
        job_available[job_id] = finish
        next_op_idx[job_id] += 1
        machine_pointer[machine_id] += 1
        push_ready_operations()

    makespan = max(operation.finish for operation in scheduled)
    return makespan, scheduled


def evaluate_solution(
    jobs: Jobs,
    machines: List[int],
    machine_sequences: MachineSequences,
) -> Tuple[int, List[ScheduledOperation]]:
    """Evalua una solucion mediante su makespan Cmax."""
    return decode_schedule(jobs, machines, machine_sequences)


def generate_neighbors(
    machine_sequences: MachineSequences,
    neighborhood_size: int,
    rng: random.Random,
) -> Iterable[Tuple[MachineSequences, Move]]:
    """Genera vecinos intercambiando prioridades en una maquina.

    Movimiento:
        Elegir una maquina y dos posiciones de su lista de prioridad; luego
        intercambiar los trabajos ubicados en esas posiciones.

    El atributo tabu se representa como:
        (machine_id, pos_i, pos_j, job_i, job_j)
    """
    machines = [machine_id for machine_id, seq in machine_sequences.items() if len(seq) >= 2]
    seen = set()
    attempts = 0
    max_attempts = neighborhood_size * 10

    while len(seen) < neighborhood_size and attempts < max_attempts:
        attempts += 1
        machine_id = rng.choice(machines)
        sequence = machine_sequences[machine_id]
        i, j = sorted(rng.sample(range(len(sequence)), 2))
        if sequence[i] == sequence[j]:
            continue

        neighbor = {mid: list(seq) for mid, seq in machine_sequences.items()}
        job_i = neighbor[machine_id][i]
        job_j = neighbor[machine_id][j]
        neighbor[machine_id][i], neighbor[machine_id][j] = job_j, job_i

        signature = tuple((mid, tuple(neighbor[mid])) for mid in sorted(neighbor))
        if signature in seen:
            continue
        seen.add(signature)

        move: Move = (machine_id, i, j, job_i, job_j)
        yield neighbor, move


def reverse_move_attribute(move: Move) -> Move:
    """Atributo tabu que representa la reversa exacta del intercambio."""
    machine_id, i, j, job_i, job_j = move
    return machine_id, i, j, job_j, job_i


def tabu_search_jssp(
    jobs: Jobs,
    machines: List[int],
    max_iterations: int = 1500,
    max_no_improvement: int = 250,
    tabu_min: int = 6,
    tabu_max: int = 14,
    neighborhood_size: int = 80,
    seed: int = 2026,
) -> Dict[str, object]:
    """Resuelve el JSSP mediante Busqueda Tabu.

    La busqueda minimiza directamente `Cmax`, ya que el decodificador siempre
    produce calendarios factibles respecto a precedencias y maquinas.
    """
    rng = random.Random(seed)
    current = build_initial_solution(jobs, machines)
    current_makespan, current_schedule = evaluate_solution(jobs, machines, current)

    best = {machine_id: list(sequence) for machine_id, sequence in current.items()}
    best_makespan = current_makespan
    best_schedule = current_schedule

    tabu_until: Dict[Move, int] = {}
    no_improvement = 0
    history: List[Tuple[int, int]] = []

    for iteration in range(1, max_iterations + 1):
        best_candidate: Optional[MachineSequences] = None
        best_candidate_move: Optional[Move] = None
        best_candidate_makespan: Optional[int] = None
        best_candidate_schedule: Optional[List[ScheduledOperation]] = None

        for candidate, move in generate_neighbors(current, neighborhood_size, rng):
            try:
                makespan, schedule = evaluate_solution(jobs, machines, candidate)
            except ValueError:
                continue

            tabu_attr = reverse_move_attribute(move)
            is_tabu = tabu_until.get(tabu_attr, -1) >= iteration
            aspiration = makespan < best_makespan

            if is_tabu and not aspiration:
                continue

            if best_candidate_makespan is None or makespan < best_candidate_makespan:
                best_candidate = candidate
                best_candidate_move = move
                best_candidate_makespan = makespan
                best_candidate_schedule = schedule

        if (
            best_candidate is None
            or best_candidate_move is None
            or best_candidate_makespan is None
            or best_candidate_schedule is None
        ):
            break

        current = best_candidate
        current_makespan = best_candidate_makespan
        current_schedule = best_candidate_schedule
        tabu_until[reverse_move_attribute(best_candidate_move)] = iteration + rng.randint(
            tabu_min, tabu_max
        )

        if current_makespan < best_makespan:
            best = {machine_id: list(sequence) for machine_id, sequence in current.items()}
            best_makespan = current_makespan
            best_schedule = current_schedule
            no_improvement = 0
        else:
            no_improvement += 1

        history.append((iteration, best_makespan))
        if no_improvement >= max_no_improvement:
            break

    return {
        "solution": best,
        "makespan": best_makespan,
        "schedule": best_schedule,
        "iterations": history[-1][0] if history else 0,
        "history": history,
    }


def print_instance(jobs: Jobs, machines: List[int]) -> None:
    """Imprime la instancia JSSP."""
    print("=== Instancia JSSP ===")
    print(f"Trabajos: {len(jobs)}")
    print(f"Maquinas: {len(machines)} -> {machines}")
    print("\nRutas tecnologicas:")
    for job_id, route in jobs.items():
        route_text = " -> ".join(
            f"M{operation.machine_id}(p={operation.processing_time})"
            for operation in route
        )
        print(f"  Trabajo {job_id}: {route_text}")


def print_solution(result: Dict[str, object], machines: List[int]) -> None:
    """Imprime la solucion JSSP por maquinas y por trabajos."""
    solution = result["solution"]
    schedule = result["schedule"]
    assert isinstance(solution, dict)
    assert isinstance(schedule, list)

    print("\n=== Resultado Busqueda Tabu JSSP ===")
    print(f"Iteraciones ejecutadas: {result['iterations']}")
    print(f"Makespan Cmax: {result['makespan']}")

    print("\nSecuencia de prioridad por maquina:")
    for machine_id in machines:
        print(f"  Maquina {machine_id}: {solution[machine_id]}")

    print("\nCalendario por maquina:")
    for machine_id in machines:
        operations = sorted(
            [operation for operation in schedule if operation.machine_id == machine_id],
            key=lambda operation: operation.start,
        )
        print(f"\nMaquina {machine_id}:")
        for operation in operations:
            print(
                f"  Trabajo {operation.job_id} - Op {operation.op_id + 1}: "
                f"inicio={operation.start}, fin={operation.finish}, "
                f"p={operation.processing_time}"
            )

    print("\nCalendario por trabajo:")
    job_ids = sorted({operation.job_id for operation in schedule})
    for job_id in job_ids:
        operations = sorted(
            [operation for operation in schedule if operation.job_id == job_id],
            key=lambda operation: operation.op_id,
        )
        route = " -> ".join(
            f"M{operation.machine_id}[{operation.start},{operation.finish}]"
            for operation in operations
        )
        print(f"  Trabajo {job_id}: {route}")


def main() -> None:
    jobs, machines = demo_instance()
    print_instance(jobs, machines)
    result = tabu_search_jssp(
        jobs,
        machines,
        max_iterations=1500,
        max_no_improvement=250,
        tabu_min=6,
        tabu_max=14,
        neighborhood_size=90,
        seed=2026,
    )
    print_solution(result, machines)


if __name__ == "__main__":
    main()
