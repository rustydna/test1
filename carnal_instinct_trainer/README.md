# CITrainer – trainer para Carnal Instinct (UE5)

Mod Lua para [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS). Busca las variables del jugador por nombre en tiempo de ejecución, así que no depende de una versión concreta del juego.

| Tecla | Función |
|-------|---------|
| F1 | Modo dios (on/off): la vida se mantiene al máximo y se activa `bCanBeDamaged = false` |
| F2 | + dinero (`MoneyAmount`) |
| F3 | Stamina/energía infinita (on/off) |
| F4 | + atributos (`StatStep`) |
| F5 | + experiencia y puntos de habilidad |
| F6 | Desbloquear todo (booleanos tipo Unlocked/Collected) y dar todos los objetos |
| F7 | Volcado: genera `dump.txt` e `items_catalog.txt` |
| F8 | Rastreador de objetos (on/off; viene apagado). Lo que se consigue va a `items_seen.log` |
| F9 | Velocidad x2 (on/off) |

## Uso rápido (3 pasos)

1. Descarga el zip y descomprímelo donde quieras.
2. Abre la carpeta `carnal_instinct_trainer` y haz doble clic en **INSTALAR.bat**. Descarga UE4SS, encuentra el juego y lo instala todo.
3. Abre el juego desde Steam, carga partida y usa **F1–F9**.

Para quitarlo, usa **DESINSTALAR.bat**. Si Windows avisa con "Windows protegió su PC", pulsa *Más información* y luego *Ejecutar de todas formas*.

## Instalación manual

1. Descarga UE4SS **para UE5** (el zip `UE4SS_v3.x.x.zip`, o el *experimental-latest* si el juego no arranca con la versión estable).
2. Busca el `.exe` que lanza realmente el juego (no el lanzador). Suele estar en
   `C:\Program Files (x86)\Steam\steamapps\common\CarnalInstinct\<NombreProyecto>\Binaries\Win64\`
   y llamarse `<NombreProyecto>-Win64-Shipping.exe`.
3. Descomprime UE4SS en esa misma carpeta `Win64` (tienen que quedar `dwmapi.dll` y la carpeta `ue4ss\`).
4. Copia la carpeta `CITrainer` de este repo en `Win64\ue4ss\Mods\`
   (en versiones antiguas de UE4SS es `Win64\Mods\`). Debe quedar
   `...\Mods\CITrainer\Scripts\main.lua` y `...\Mods\CITrainer\enabled.txt`.
5. Para ver los mensajes del trainer, en `UE4SS-settings.ini` pon `GuiConsoleEnabled = 1` y `GuiConsoleVisible = 1`.
6. Arranca el juego y carga una partida. En la consola debe salir `[CITrainer] Cargado.`

## Si algo no hace efecto

No he podido probarlo contra el juego, así que los nombres de las variables los adivina con patrones genéricos (`health`, `gold`, `money`, `stamina`...). Si una tecla dice "no se encontró ninguna variable" o cambia lo que no es:

1. Pulsa **F7** con la partida cargada.
2. Abre `Mods\CITrainer\dump.txt`: verás todas las variables del jugador, componentes, PlayerState, GameInstance y SaveGame con su tipo y valor actual, además de las funciones disponibles.
3. Busca el nombre real (p.ej. `Coins`, `CurrentHP`) y ponlo en `Exact` de la categoría correspondiente en `Scripts\config.lua`:
   ```lua
   Money = { Patterns = {...}, Exact = { "Coins" } },
   ```
4. Recarga los mods con Ctrl+R en la consola de UE4SS, o reinicia el juego.

### Dar todos los objetos (F6)

El trainer busca una función tipo `AddItem` / `GiveItem` / `AddToInventory` en el jugador y sus componentes. Si el primer parámetro es un objeto o clase de ítem, la llama con cada asset compatible que esté cargado en memoria. Si no la encuentra o la firma no es reconocible:

- Mira la sección `== FUNCIONES ==` de `dump.txt` y rellena `GiveAll.Object` / `GiveAll.Function` en `config.lua`.
- Sólo se ven los assets cargados. Para tener el máximo, pulsa F6 en una zona donde ya existan, o añade rutas en `PreloadAssets` (sacadas de `items_catalog.txt`).

### Rastreador de objetos

Cada 2 segundos revisa los arrays y mapas de inventario, colección y galería, y apunta cada entrada nueva en `items_seen.log`. Así ves cómo se llaman internamente los objetos y desbloqueos que vas consiguiendo. Si conoces la función de recogida (por ejemplo `BP_Pickup_C:OnPickedUp`, que sale en el dump), añádela a `ItemPickupHooks` para registrar cada recogida con sus argumentos.

## Notas

- Haz copia de tu partida (`%LOCALAPPDATA%\<NombreProyecto>\Saved\SaveGames`) antes de usar F6.
- El modo dios fija la vida del personaje a su máximo. Si el juego usa GAS (`GameplayAttributeData`), también lo soporta.
