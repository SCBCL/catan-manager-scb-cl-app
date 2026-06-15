🏆 App Catan Manager

¡Bienvenido al gestor para torneos de Catan! 🎲

Esta aplicación es una herramienta diseñada para organizar, gestionar y llevar el control de torneos de Catan de forma automática, permitiendo manejar desde inscripciones hasta el cálculo de puntos y la gestión de fases finales (semifinales y gran final).

🚀 Características

Gestión de Jugadores: Carga masiva mediante Excel o inscripción manual.

Motor de Rondas: Generación automática de mesas (Sistemas Aleatorio, Suizo y P16).

Ranking en tiempo real: Cálculo automático de Puntos de Victoria (PV), Puntos de Mesa (PM) y Rendimiento.

Sistema de Apuestas: Funcionalidad de "Tote Blindado" para finales.

Temporizador integrado: Control de tiempo para tus partidas.

Exportación: Generación de reportes en Excel y carteles de fixture.

📥 Instalación

Ve a la sección de [Releases] en este repositorio.

Descarga el archivo Instalador_Catan_Manager.exe.

Ejecuta el instalador y sigue las instrucciones en pantalla.

Se creará un acceso directo en tu escritorio para abrir la aplicación directamente.

🛠️ Cómo compilar desde el código (Para desarrolladores)

Si deseas modificar el código y compilar tu propia versión:

Instala las dependencias: pip install -r requirements.txt (o instala PyInstaller).

Compila el ejecutable con PyInstaller:

pyinstaller --onefile --windowed --collect-all streamlit --name "App Catan Manager" app.py


Usa este script en Inno Setup para generar el instalador final.

⚖️ Licencia

Este proyecto se distribuye bajo la Licencia MIT. Siéntete libre de usarlo, modificarlo y compartirlo.

📝 Créditos

Desarrollado por Simón Carvajal B. (Catan Universe Chile).
Agradecimientos especiales a Odette Garrido, Loreto Gacitua y La Secata.

Hecho en Chile, 2025.
