# HF-DRSP con Busqueda Tabu

Este proyecto contiene un script en Python para resolver una instancia del problema de secuenciacion y ruteo de drones de entrega con flota heterogenea y tiempos de recarga.

El ejercicio se desarrolla con fines academicos como solucion de un taller de la asignatura Modelos de Optimizacion Avanzada, en el marco de la doble titulacion en Maestria en Ingenieria en Internet de las Cosas y Maestria en Inteligencia Artificial.

El archivo principal es:

```bash
hf_drsp_tabu.py
```

El archivo para generar graficas es:

```bash
plot_hf_drsp_solution.py
```

## Requisitos

- Python 3.9 o superior.
- `matplotlib` para generar las graficas de rutas y el diagrama de Gantt.

## 1. Crear el entorno virtual

Desde la carpeta del proyecto, ejecutar:

```bash
python3 -m venv .venv
```

En Windows, si `python3` no funciona, usar:

```bash
python -m venv .venv
```

## 2. Activar el entorno virtual

En macOS o Linux:

```bash
source .venv/bin/activate
```

En Windows PowerShell:

```bash
.venv\Scripts\Activate.ps1
```

En Windows CMD:

```bash
.venv\Scripts\activate.bat
```

## 3. Instalar requerimientos

El script principal de optimizacion usa solo librerias estandar de Python. Para generar las graficas se requiere `matplotlib`, incluido en `requirements.txt`.

Ejecutar:

```bash
pip install -r requirements.txt
```

## 4. Ejecutar el script

Con el entorno virtual activo, ejecutar:

```bash
python hf_drsp_tabu.py
```

En algunos sistemas tambien puede usarse:

```bash
python3 hf_drsp_tabu.py
```

## 5. Generar graficas

Para generar las graficas de la solucion reportada en `result.txt`, ejecutar:

```bash
python plot_hf_drsp_solution.py
```

En algunos sistemas tambien puede usarse:

```bash
python3 plot_hf_drsp_solution.py
```

El script genera los siguientes archivos dentro de la carpeta `figures`:

```text
figures/misiones_drones.png
figures/gantt_misiones.png
```

La primera grafica muestra la ubicacion del centro de distribucion, los clientes y las rutas de cada mision por dron. La segunda grafica muestra el diagrama de Gantt, donde se observan los periodos de vuelo y los tiempos de recarga entre misiones.

Si se desea recalcular la solucion mediante Busqueda Tabu antes de graficar, ejecutar:

```bash
python plot_hf_drsp_solution.py --resolve
```

### Visualizacion de rutas y misiones

La siguiente figura representa espacialmente la solucion. El centro de distribucion aparece como `CD` en el origen `(0, 0)`, los clientes aparecen identificados por su numero de pedido y las lineas de color muestran las misiones asignadas a cada dron. Cada ruta inicia en el centro de distribucion, visita los clientes de la mision en el orden indicado y retorna al centro.

![Ubicacion de clientes y rutas de misiones por dron](figures/misiones_drones.png)

Esta grafica permite observar la logica geografica de la asignacion: los pedidos mas alejados o agrupados en zonas compatibles tienden a ser atendidos por drones con mayor autonomia, mientras que los drones con menor capacidad y bateria se concentran en misiones mas cortas. Tambien permite identificar visualmente rutas cercanas a los limites de autonomia, como ocurre con algunas misiones del Dron 4.

### Diagrama de Gantt de la solucion

La siguiente figura muestra la programacion temporal de las misiones. Las barras de color representan los periodos de vuelo de cada dron y las barras sombreadas representan los tiempos de recarga entre misiones consecutivas. La linea vertical punteada marca el `Cmax`, es decir, el instante en que finaliza la ultima mision del sistema.

![Diagrama de Gantt de misiones y recargas](figures/gantt_misiones.png)

El diagrama de Gantt permite interpretar el componente de scheduling del problema. Aunque los drones operan en paralelo, cada dron debe respetar su secuencia interna de misiones y los tiempos de recarga. En la solucion reportada, el Dron 3 define el makespan porque su segunda mision finaliza en `66.64`, mientras los demas drones terminan antes.

## 6. Resultado esperado

El script imprime en consola:

- La instancia del problema: drones, capacidades, autonomias, tiempos de recarga y pedidos.
- El resultado de la Busqueda Tabu.
- El makespan `Cmax`.
- La funcion objetivo penalizada.
- Excesos de capacidad y bateria.
- El plan de misiones por cada dron.

Ejemplo de salida:

```text
=== Resultado Busqueda Tabu ===
Iteraciones ejecutadas: 661
Makespan Cmax: 66.64
Funcion objetivo penalizada: 66.64
Exceso total capacidad: 0.00
Exceso total bateria: 0.00
```

## 7. Modificar la instancia

Los datos de prueba se encuentran dentro de la funcion `demo_instance()` en `hf_drsp_tabu.py`.

Alli se pueden modificar:

- Coordenadas de los pedidos.
- Peso o demanda de cada pedido.
- Numero de drones.
- Capacidad maxima `capacity`.
- Autonomia `battery`.
- Tiempo de recarga `recharge`.

## 8. Desactivar el entorno virtual

Cuando se termine de trabajar:

```bash
deactivate
```

## 9. Analisis del resultado obtenido

### Enunciado del problema

Una empresa de logistica de ultima milla opera desde un centro de distribucion ubicado en el punto `(0, 0)` y debe entregar un conjunto de pedidos a diferentes clientes de la ciudad. Para realizar las entregas dispone de una flota heterogenea de drones. Cada dron `k` cuenta con tres parametros operativos principales: capacidad maxima de carga `Q_k`, autonomia de vuelo `B_k` y tiempo de recarga `R_k`.

Una mision corresponde al recorrido que inicia en el centro de distribucion, visita uno o varios clientes, entrega sus pedidos y retorna nuevamente al centro de distribucion. Para que una mision sea factible, la suma de las cargas transportadas no debe superar la capacidad del dron asignado y la distancia total recorrida no debe exceder su autonomia disponible. Cuando un dron finaliza una mision, queda indisponible durante su tiempo de recarga antes de poder ejecutar una nueva mision.

El objetivo del problema es determinar simultaneamente:

- La asignacion de pedidos a drones.
- La agrupacion de pedidos en misiones.
- El orden de visita de los clientes dentro de cada mision.
- La secuencia temporal de misiones para cada dron.

La funcion objetivo es minimizar el `makespan` `Cmax`, definido como el instante en que el ultimo dron finaliza su ultima mision y regresa al centro de distribucion. En otras palabras, se busca completar todas las entregas en el menor tiempo total posible, respetando capacidad, autonomia y recarga.

El archivo `result.txt` contiene la salida de una ejecucion del algoritmo de Busqueda Tabu aplicado al problema HF-DRSP (Heterogeneous Fleet Drone Routing and Scheduling Problem). Este problema integra dos familias clasicas de optimizacion combinatoria:

- Un problema de ruteo de vehiculos con flota heterogenea, porque cada dron tiene capacidad de carga `Q_k`, autonomia `B_k` y caracteristicas operativas distintas.
- Un problema de secuenciacion en maquinas paralelas no identicas, porque cada dron actua como una maquina/recurso que procesa una secuencia de misiones y queda indisponible durante su tiempo de recarga `R_k`.

La dificultad del problema no esta solamente en asignar pedidos a drones, sino en decidir simultaneamente como agrupar pedidos en misiones, en que orden visitarlos, que dron debe ejecutar cada mision y como la recarga afecta el tiempo total de finalizacion. Esta integracion justifica el uso de una metaheuristica, ya que el espacio de busqueda crece rapidamente con el numero de pedidos, drones y posibles particiones de rutas.

### Resumen numerico de la ejecucion

La ejecucion reportada finalizo despues de 661 iteraciones. El resultado principal fue:

```text
Makespan Cmax: 66.64
Funcion objetivo penalizada: 66.64
Exceso total capacidad: 0.00
Exceso total bateria: 0.00
Alpha final: 5.00 | Beta final: 2.00
```

El hecho de que la funcion objetivo penalizada sea igual al makespan indica que la solucion final no presenta violaciones de restricciones. En terminos de la funcion:

```text
F(S) = Cmax + alpha * exceso_capacidad + beta * exceso_bateria
```

se tiene:

```text
F(S) = 66.64 + alpha * 0.00 + beta * 0.00 = 66.64
```

Por tanto, la solucion encontrada es factible respecto a las restricciones fisicas y operativas del sistema: capacidad de carga, autonomia de bateria y secuenciacion de recargas entre misiones.

### Interpretacion de la solucion encontrada

La asignacion final de pedidos fue:

```text
Dron 1: [8], [12]
Dron 2: [6], [2, 1], [4]
Dron 3: [10, 13, 11], [7, 14, 15]
Dron 4: [9, 5], [3]
```

Esta estructura corresponde a la codificacion definida para el problema: cada fila representa un dron y cada lista interna representa una mision ejecutada cronologicamente. La solucion cubre los pedidos del 1 al 15 exactamente una vez, por lo que cumple la restriccion de cobertura total de la demanda.

La distribucion tambien muestra que el algoritmo no realiza una asignacion uniforme en cantidad de pedidos, sino una asignacion condicionada por la heterogeneidad de la flota. Esto es importante: en flotas heterogeneas, balancear el numero de pedidos por dron no garantiza una buena solucion. Lo relevante es balancear carga, distancia, autonomia, tiempo de recarga y tiempo de finalizacion.

Las figuras incluidas en la seccion de generacion de graficas complementan esta lectura. El mapa de misiones permite analizar la distribucion espacial de las rutas, mientras que el diagrama de Gantt permite evaluar la dimension temporal del problema y detectar que recurso determina el `Cmax`.

### Analisis por dron

#### Dron 1

```text
Mision 1: [8]  | fin = 22.80 | carga = 1.80 | distancia = 22.80
Mision 2: [12] | fin = 49.16 | carga = 2.40 | distancia = 22.36
```

El Dron 1 atiende pedidos individuales ubicados relativamente lejos del centro de distribucion. Aunque su capacidad es `5.0`, la autonomia `25.0` restringe la posibilidad de agrupar estos pedidos con otros clientes sin comprometer la factibilidad de bateria. En este caso, el algoritmo privilegia rutas individuales para conservar la factibilidad energetica.

#### Dron 2

```text
Mision 1: [6]    | fin = 18.97 | carga = 1.50 | distancia = 18.97
Mision 2: [2, 1] | fin = 38.37 | carga = 3.40 | distancia = 16.40
Mision 3: [4]    | fin = 59.81 | carga = 2.80 | distancia = 18.44
```

El Dron 2 ejecuta tres misiones. A pesar de tener una capacidad y autonomia intermedias, su tiempo de recarga es bajo (`R = 3.0`), lo que le permite procesar mas misiones sin convertirse en el recurso critico. Este comportamiento es coherente con la logica de scheduling: un recurso con menor tiempo de preparacion puede absorber mas trabajos si las duraciones individuales no son excesivas.

#### Dron 3

```text
Mision 1: [10, 13, 11] | fin = 31.52 | carga = 6.20 | distancia = 31.52
Recarga: 6.00
Mision 2: [7, 14, 15]  | fin = 66.64 | carga = 5.40 | distancia = 29.12
```

El Dron 3 es el dron de mayor capacidad (`Q = 7.0`) y mayor autonomia (`B = 32.0`). Por esta razon, el algoritmo le asigna las misiones mas exigentes en distancia y carga. Sin embargo, tambien tiene el mayor tiempo de recarga (`R = 6.0`), lo que incrementa su tiempo acumulado.

Este dron define el makespan de la solucion:

```text
Cmax = 66.64
```

Por tanto, el Dron 3 es el cuello de botella del sistema. En terminos de optimizacion, cualquier mejora relevante sobre la solucion actual deberia intentar reducir el tiempo total de este dron, ya sea reasignando algun pedido de su segunda mision o encontrando una ruta equivalente con menor distancia.

#### Dron 4

```text
Mision 1: [9, 5] | fin = 16.49 | carga = 3.30 | distancia = 16.49
Mision 2: [3]    | fin = 34.62 | carga = 1.20 | distancia = 16.12
```

El Dron 4 tiene la menor capacidad (`Q = 3.5`) y la menor autonomia (`B = 17.0`). La solucion lo usa para misiones cortas y de baja carga. La primera mision queda muy cerca de sus limites: carga `3.30` sobre `3.50` y distancia `16.49` sobre `17.00`. Esto evidencia que el algoritmo explota de forma eficiente el recurso sin violar restricciones.

### Evaluacion de factibilidad

La solucion final es factible por tres razones:

- Cobertura: los 15 pedidos son atendidos exactamente una vez.
- Capacidad: ninguna mision supera la capacidad maxima del dron asignado.
- Autonomia: ninguna ruta supera la autonomia disponible del dron.

Adicionalmente, la secuenciacion respeta los tiempos de recarga. Por ejemplo, el Dron 3 finaliza su primera mision en `31.52`, permanece en recarga durante `6.00` unidades de tiempo e inicia su segunda mision en `37.52`. Este patron se observa tambien en los demas drones con mas de una mision.

Desde una perspectiva de sistemas IoT, la restriccion de recarga puede interpretarse como un periodo de indisponibilidad fisica del dispositivo. En una implementacion real, este dato podria provenir de telemetria de bateria, estaciones de carga inteligentes o modelos predictivos de degradacion energetica.

### Comportamiento de la Busqueda Tabu

El algoritmo no se limita a una busqueda greedy. La Busqueda Tabu permite explorar vecinos generados por movimientos de intercambio e insercion, evitando ciclos mediante memoria de corto plazo. En esta implementacion, la memoria tabu registra atributos del tipo:

```text
(ID_Pedido, ID_Dron)
```

Esto impide que un pedido retorne inmediatamente al dron del cual fue removido, reduciendo oscilaciones improductivas. El tenor tabu dinamico, elegido aleatoriamente entre 7 y 15 iteraciones, introduce diversificacion y evita que la busqueda siga siempre el mismo patron determinista.

La presencia de penalizaciones dinamicas `alpha` y `beta` permite aceptar temporalmente soluciones infactibles durante el proceso de busqueda. Esta estrategia es relevante en optimizacion avanzada porque algunas regiones de soluciones factibles pueden estar separadas por soluciones intermedias infactibles. Permitir esa exploracion controlada aumenta la probabilidad de escapar de optimos locales.

En la salida final, `alpha = 5.00` y `beta = 2.00`, que son los valores minimos alcanzados despues de encontrar soluciones factibles sostenidas. Esto sugiere que hacia el final de la busqueda la solucion se mantuvo dentro de la region factible y ya no fue necesario castigar fuertemente las violaciones.

### Interpretacion desde inteligencia artificial

Desde la Maestria en Inteligencia Artificial, la Busqueda Tabu puede analizarse como una tecnica de busqueda local inteligente con memoria adaptativa. Aunque no aprende un modelo estadistico, si incorpora mecanismos propios de IA simbolica y metaheuristica:

- Memoria de corto plazo para evitar ciclos.
- Criterio de aspiracion para aceptar movimientos tabu si producen una mejora global.
- Exploracion de vecindarios mediante operadores de transformacion.
- Penalizacion adaptativa para balancear factibilidad y calidad de solucion.

El algoritmo representa una alternativa razonable cuando no se busca una prueba exacta de optimalidad, sino una solucion factible de buena calidad en un tiempo computacional controlado.

### Conclusiones

La solucion obtenida es consistente con el planteamiento academico del HF-DRSP, ya que integra decisiones de ruteo, asignacion y secuenciacion bajo restricciones de capacidad, autonomia y recarga. El valor `Cmax = 66.64` representa el tiempo necesario para completar todas las entregas, considerando que los drones pueden operar en paralelo pero cada uno debe respetar su propia secuencia de misiones.

El resultado demuestra que la flota heterogenea se utiliza de manera diferenciada: los drones con mayor autonomia absorben rutas mas exigentes, mientras que los drones pequenos son asignados a misiones cercanas o de baja carga. Esta asignacion es coherente con el comportamiento esperado de un sistema logistico basado en drones.

El cuello de botella se encuentra en el Dron 3. Aunque es el recurso mas capaz, su combinacion de misiones largas y recarga elevada determina el tiempo final del sistema. Por tanto, una mejora futura deberia concentrarse en reducir el tiempo acumulado de ese dron sin trasladar infactibilidad a los demas recursos.

Finalmente, el uso de Busqueda Tabu es adecuado para el contexto del taller porque permite abordar un problema NP-duro mediante una tecnica metaheuristica interpretable, parametrizable y extensible. Para trabajos posteriores se podrian comparar los resultados contra otras estrategias como Algoritmos Geneticos, Recocido Simulado, GRASP o modelos MILP para instancias pequenas, con el fin de evaluar calidad de solucion, estabilidad y tiempo computacional.
