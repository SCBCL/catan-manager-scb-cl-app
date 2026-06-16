# 🎲 Catan Manager - Sistema Gestor de Torneos

Un avanzado sistema de gestión y automatización de torneos de Catan, diseñado con una interfaz gráfica en Streamlit. Esta herramienta abarca desde la inscripción de jugadores hasta la coronación del campeón, integrando emparejamientos inteligentes, cálculo automático de rendimientos, fases finales con ventaja deportiva y un sistema de apuestas dinámico. De Chile para el mundo.

Contacto: simon.carvajal24@gmail.com

---

## 🚀 Características Principales

* **Auto-Configurable:** Script inteligente que instala sus propias dependencias automáticamente al ejecutarse.
* **Persistencia Segura:** Guardado automático (Auto-Save) y generación de respaldos locales por fecha.
* **Emparejamiento Avanzado:** Sistemas de fixture Aleatorio, Suizo y P16, con prevención de choque de equipos y control de repetición de rivales.
* **Exportación Fácil:** Genera capturas de pantalla de los fixtures y clasificaciones, y exporta toda la data a Excel.
* **Herramientas de Evento:** Temporizador flotante con alarmas, sorteos interactivos y generador de mapas integrado.

---

## 📥 Instalación y Ejecución

El código cuenta con un **Bootstrapper (Auto-Instalador)**, lo que significa que no necesitas instalar las librerías manualmente. 

**Paso a Paso:**
1. Instala [Python 3.8+](https://www.python.org/downloads/) en tu sistema.
2. Descarga el archivo principal del código (ej. `catan_manager.py`).
3. Abre una terminal o línea de comandos en la carpeta donde descargaste el archivo.
4. Ejecuta el siguiente comando:
   ```bash
   python catan_manager.py

***📖 Manual de Uso y Funcionalidades***
1. Gestión de Jugadores (Inscripción)
El sistema permite administrar el padrón de participantes en la fase "Clasificatoria".

**Cargar Información:** Puedes agregar jugadores manualmente uno por uno (indicando nombre y equipo) o subir un archivo Excel (.xlsx) con una lista masiva de participantes (el listado debe tener como titulo jugadores).

**Editar:** Utiliza el buscador integrado para localizar a un jugador. El botón del lápiz (✏️) te permite corregir su nombre o cambiarlo de equipo en tiempo real sin perder su historial.

**Eliminar:** Puedes borrar jugadores individuales (botón 🗑️) ante inasistencias de último minuto (el sistema reajustará las mesas automáticamente) o vaciar la lista completa para iniciar un nuevo evento.

***2. Generador de Rondas y Mesas***
El corazón del torneo. Soporta mesas de 4 y 3 jugadores (priorizando siempre las de 4). Tienes tres motores de emparejamiento:

Aleatorio: Ideal para menos de 12 jugadores. Mezcla los jugadores evitando que los miembros de un mismo equipo se enfrenten y minimizando la repetición de rivales.

Sistema Suizo: Ideal para 12 o más jugadores. A partir de la segunda ronda, empareja a los jugadores según su posición en la tabla (fuerte contra fuerte), garantizando un Top 4 verdaderamente competitivo.

Aleatorio P16: Sistema estricto para 16+ jugadores que asegura equidad total en los turnos de juego (1º, 2º, 3º y 4º lugar de asiento) a lo largo de 4 rondas sin repetir rivales (standart clasificatorio nacional).

Gestión Manual: Permite intercambiar (swap) jugadores entre mesas ya generadas si la organización lo requiere de forma excepcional.

Ademas genera una imagen para copiar y pegar a traves de wzp.

***3. Registro de Resultados***
Ingreso rápido y seguro de los puntajes obtenidos en cada partida.

Solo debes ingresar los Puntos de Mesa (PM) de cada jugador.

El sistema calcula automáticamente los Puntos de Victoria (PV) (1.0 para el ganador, 0.5 para empate de 2, etc.) y el Rendimiento (%V).

Ajuste de Mesas de 3: El sistema incluye un jugador fantasma estadístico para que el %V no se infle injustamente frente a las mesas de 4 jugadores.

***4. Clasificación General***
Tabla de posiciones en tiempo real. Los criterios de desempate técnicos y automáticos son:

Estado: Jugadores Activos por encima de retirados/eliminados.

PV (Puntos de Victoria).
PM (Puntos de Mesa Totales).
%V (Porcentaje de Victorias).
Cantidad de 2dos y 3ros lugares.

***5. Fases Finales (Semifinales y Final)***
Transición fluida a las llaves eliminatorias.

Automático: El sistema detecta el aforo. Si hay de 12 a 28 jugadores, genera una Final Directa. Si hay 29 o más, genera un Top 16 (4 Semifinales).

Forzado Manual: Puedes obligar al sistema a crear Semis o Final Directa según criterio de la organización.

Ventaja Deportiva: El sistema asigna los lugares (Seeds) informando en pantalla el orden estricto de elección de turno, asiento y color de fichas basado en la Tabla General.

Reemplazos: Si un jugador abandona en Fase Final, el sistema lo reemplaza automáticamente por el siguiente mejor de la tabla general o el 2do lugar de su semifinal de origen.

***6. Sistema de Apuestas***
Activable únicamente en la Gran Final, permite a los jugadores eliminados apostar dinero ficticio (o fichas) por los finalistas.

Cuotas Dinámicas: El pago varía en tiempo real. Si un jugador recibe muchas apuestas, su cuota baja. Si recibe pocas, su cuota sube.

Topes y Pisos: El sistema protege "la banca" con un pago máximo de x3.5 y garantiza un retorno mínimo al apostador.

Liquidación: Al coronar al campeón, el gestor reparte los premios matemáticamente y muestra las ganancias de la casa y los apostadores en un registro detallado.

***7. Sorteo de Premios (Tómbola)***
Módulo para seleccionar azares entre todos los jugadores activos que no hayan sido eliminados.

Cuenta regresiva visual.

Efectos de sonido integrados (redoble de tambores y aplausos).

Entrega 1 ganador principal y 2 suplentes inmediatos en caso de ausencia.

***8. Utilidades Adicionales***
Temporizador: Reloj en pantalla de 45', 60' o personalizado. Flota en la barra lateral para ser visible mientras se navega, permite pausas, añade minutos de compensación y dispara una alarma visual/sonora al llegar a cero.

Generador de Mapas: Integra el generador de Jamison Bunge directamente en el software para armar los tableros de cada ronda.

**⚖️ Avisos y Derechos**
Aviso Legal Catan®:
Catan® es una marca registrada de Catan GmbH y Catan Studio. Este software es una herramienta de asistencia independiente creada para y por la comunidad. No existe explotación comercial, ni lucro sobre la propiedad intelectual de terceros. La organización de eventos que utilicen este software no actúa como representante comercial de Catan GmbH, Asmodee ni Devir.

**Aviso de Terceros:**
La herramienta "Catan Board Generator" integrada mediante iFrame en este sistema es propiedad intelectual exclusiva de Jamison Bunge (catan.bunge.io).

👨‍💻 Créditos
Desarrollo y Arquitectura de Software: **Simón Carvajal B.**
Organización / Comunidad: Catan Universe Chile

Agradecimientos Especiales a:

Odette Garrido

Loreto Gacitua y La Secata

© 2025 Sistema APP Manager Chile. Todos los derechos reservados. Licencia de uso gratuito sujeta a la atribución del autor original.
