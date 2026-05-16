#!/usr/bin/env python3
"""
Genera graficas para la solucion HF-DRSP:
- Ubicacion y rutas de las misiones por dron.
- Diagrama de Gantt con vuelos y recargas.
- Curva de convergencia de la Busqueda Tabu.

Ejecutar:
    python3 plot_hf_drsp_solution.py

Opcionalmente, recalcular la solucion con Busqueda Tabu:
    python3 plot_hf_drsp_solution.py --resolve
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from hf_drsp_tabu import (
    Customer,
    Drone,
    Solution,
    demo_instance,
    evaluate_solution,
    tabu_search,
)


# Solucion reportada en result.txt.
REPORTED_SOLUTION: Solution = [
    [[8], [12]],
    [[6], [2, 1], [4]],
    [[10, 13, 11], [7, 14, 15]],
    [[9, 5], [3]],
]


DRONE_COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd"]
MISSION_MARKERS = ["o", "s", "^", "D", "P", "X"]


def coordinates_for_route(
    mission: List[int],
    customers: Dict[int, Customer],
) -> Tuple[List[float], List[float]]:
    x_values = [0.0]
    y_values = [0.0]
    for customer_id in mission:
        customer = customers[customer_id]
        x_values.append(customer.x)
        y_values.append(customer.y)
    x_values.append(0.0)
    y_values.append(0.0)
    return x_values, y_values


def plot_mission_map(
    solution: Solution,
    drones: List[Drone],
    customers: Dict[int, Customer],
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(11, 8))

    ax.scatter(
        [0],
        [0],
        marker="*",
        s=260,
        color="#111111",
        label="Centro de distribucion",
        zorder=5,
    )
    ax.annotate("CD", (0, 0), xytext=(8, 8), textcoords="offset points", weight="bold")

    for customer in customers.values():
        ax.scatter(customer.x, customer.y, s=55, color="#f2f2f2", edgecolor="#333333", zorder=4)
        ax.annotate(
            str(customer.id),
            (customer.x, customer.y),
            xytext=(6, 5),
            textcoords="offset points",
            fontsize=9,
        )

    for drone_idx, missions in enumerate(solution):
        color = DRONE_COLORS[drone_idx % len(DRONE_COLORS)]
        for mission_idx, mission in enumerate(missions):
            x_values, y_values = coordinates_for_route(mission, customers)
            marker = MISSION_MARKERS[mission_idx % len(MISSION_MARKERS)]
            label = f"Dron {drones[drone_idx].id} - Mision {mission_idx + 1}: {mission}"

            ax.plot(
                x_values,
                y_values,
                color=color,
                linewidth=2.0,
                marker=marker,
                markersize=6,
                alpha=0.85,
                label=label,
            )

            for order, customer_id in enumerate(mission, start=1):
                customer = customers[customer_id]
                ax.annotate(
                    f"{order}",
                    (customer.x, customer.y),
                    xytext=(-12, -12),
                    textcoords="offset points",
                    fontsize=8,
                    color=color,
                    weight="bold",
                )

    ax.set_title("Ubicacion de clientes y rutas de misiones por dron", fontsize=14, weight="bold")
    ax.set_xlabel("Coordenada X")
    ax.set_ylabel("Coordenada Y")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.45)
    ax.set_aspect("equal", adjustable="box")
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8, frameon=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_gantt_chart(
    solution: Solution,
    drones: List[Drone],
    schedule,
    makespan: float,
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 6.5))
    bar_height = 0.55

    for drone_idx, missions in enumerate(solution):
        y_position = len(solution) - drone_idx
        color = DRONE_COLORS[drone_idx % len(DRONE_COLORS)]
        drone = drones[drone_idx]

        for mission_idx, mission in enumerate(missions):
            mission_eval = schedule[drone_idx][mission_idx]
            duration = mission_eval.finish - mission_eval.start

            ax.barh(
                y_position,
                duration,
                left=mission_eval.start,
                height=bar_height,
                color=color,
                edgecolor="#222222",
                alpha=0.9,
            )
            ax.text(
                mission_eval.start + duration / 2,
                y_position,
                f"M{mission_idx + 1}: {mission}",
                ha="center",
                va="center",
                color="white",
                fontsize=9,
                weight="bold",
            )

            if mission_idx < len(missions) - 1:
                recharge_start = mission_eval.finish
                recharge_duration = drone.recharge
                ax.barh(
                    y_position,
                    recharge_duration,
                    left=recharge_start,
                    height=bar_height,
                    color="#dddddd",
                    edgecolor="#666666",
                    hatch="//",
                    alpha=0.85,
                )
                ax.text(
                    recharge_start + recharge_duration / 2,
                    y_position - 0.36,
                    f"R={recharge_duration:.0f}",
                    ha="center",
                    va="center",
                    color="#333333",
                    fontsize=8,
                )

    ax.axvline(makespan, color="#111111", linestyle="--", linewidth=1.6)
    ax.text(
        makespan,
        len(solution) + 0.65,
        f"Cmax = {makespan:.2f}",
        ha="right",
        va="center",
        fontsize=10,
        weight="bold",
    )

    ax.set_title("Diagrama de Gantt de misiones y recargas", fontsize=14, weight="bold")
    ax.set_xlabel("Tiempo")
    ax.set_ylabel("Dron")
    ax.set_yticks(range(1, len(solution) + 1))
    ax.set_yticklabels([f"Dron {drone.id}" for drone in reversed(drones)])
    ax.set_xlim(0, makespan * 1.08)
    ax.grid(True, axis="x", linestyle="--", linewidth=0.5, alpha=0.45)
    ax.legend(
        handles=[
            Patch(facecolor=DRONE_COLORS[0], edgecolor="#222222", label="Mision de vuelo"),
            Patch(facecolor="#dddddd", edgecolor="#666666", hatch="//", label="Recarga"),
        ],
        loc="lower right",
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_convergence(history, output_path: Path) -> None:
    """Genera la curva de convergencia del mejor Cmax factible historico."""
    fig, ax = plt.subplots(figsize=(10, 5.5))

    if history:
        feasible_history = [item for item in history if len(item) > 5 and item[5] is not None]
    else:
        feasible_history = []

    if feasible_history:
        iterations = [item[0] for item in feasible_history]
        best_makespan_values = [item[5] for item in feasible_history]
        ax.plot(iterations, best_makespan_values, color="#1f77b4", linewidth=2.2)
        ax.scatter(iterations[-1], best_makespan_values[-1], color="#d62728", zorder=4)
        ax.annotate(
            f"Mejor Cmax = {best_makespan_values[-1]:.2f}",
            (iterations[-1], best_makespan_values[-1]),
            xytext=(-125, 20),
            textcoords="offset points",
            fontsize=10,
            weight="bold",
            arrowprops={"arrowstyle": "->", "color": "#333333"},
        )

    ax.set_title("Convergencia factible de la Busqueda Tabu para HF-DRSP", fontsize=14, weight="bold")
    ax.set_xlabel("Iteracion")
    ax.set_ylabel("Mejor Cmax factible historico")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.45)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def compute_convergence_history():
    """Ejecuta Busqueda Tabu para obtener el historial de convergencia."""
    drones, customers, distances = demo_instance()
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
    return result["history"]


def solve_or_load_reported_solution(resolve: bool):
    drones, customers, distances = demo_instance()
    if resolve:
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
        solution = result["solution"]
        makespan = result["makespan"]
        schedule = result["schedule"]
        source = "solucion recalculada con Busqueda Tabu"
    else:
        solution = REPORTED_SOLUTION
        _, makespan, capacity_excess, battery_excess, schedule = evaluate_solution(
            solution,
            drones,
            customers,
            distances,
            alpha=5.0,
            beta=2.0,
        )
        if capacity_excess > 0.0 or battery_excess > 0.0:
            raise ValueError("La solucion reportada no es factible para la instancia actual.")
        source = "solucion reportada en result.txt"

    return drones, customers, solution, schedule, makespan, source


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera graficas de rutas y Gantt para la solucion HF-DRSP."
    )
    parser.add_argument(
        "--resolve",
        action="store_true",
        help="Recalcula la solucion con Busqueda Tabu antes de graficar.",
    )
    parser.add_argument(
        "--output-dir",
        default="figures",
        help="Carpeta donde se guardaran las graficas. Valor por defecto: figures.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    drones, customers, solution, schedule, makespan, source = solve_or_load_reported_solution(
        args.resolve
    )

    map_path = output_dir / "misiones_drones.png"
    gantt_path = output_dir / "gantt_misiones.png"
    convergence_path = output_dir / "hf_drsp_convergencia.png"

    plot_mission_map(solution, drones, customers, map_path)
    plot_gantt_chart(solution, drones, schedule, makespan, gantt_path)
    plot_convergence(compute_convergence_history(), convergence_path)

    print(f"Fuente: {source}")
    print(f"Makespan Cmax: {makespan:.2f}")
    print(f"Grafica de misiones: {map_path}")
    print(f"Diagrama de Gantt: {gantt_path}")
    print(f"Curva de convergencia: {convergence_path}")


if __name__ == "__main__":
    main()
