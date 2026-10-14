# SL Rigger para Blender

Add-on de Blender (en la línea de Avastar o Bento Buddy) para convertir mallas 3D en
**avatares y ropa rigged** y en **objetos estáticos** listos para subir a **Second Life**.

Formatos de exportación:

* **Collada `.dae`**: exportador propio (Blender ya no trae el suyo). Es el formato
  recomendado para avatares y ropa rigged.
* **glTF `.glb` / `.gltf`**: lo acepta el subidor de modelos de SL desde el visor 2025.05
  (también Firestorm). Recomendado para objetos estáticos.
* **Materiales PBR `.glb`**: un archivo por material para *Build → Upload → Material*.

## Ediciones

| Edición | Blender | Paquete |
|---|---|---|
| **Founder Edition** | 3.5 o superior | `sl_rigger_founder_X.Y.Z.zip` (complemento clásico) |
| **Standard Edition** | 4.2 o superior (incluido 5.x) | `sl_rigger_standard_X.Y.Z.zip` (extensión) |

Las dos salen del mismo código con `python build.py` (se escriben en `dist/`).

## Instalación

* **Founder (Blender 3.5–4.1):** *Editar → Preferencias → Complementos → Instalar…*, elige el zip y activa **SL Rigger**.
* **Standard (Blender 4.2+):** *Editar → Preferencias → Extensiones → ⌄ → Instalar desde disco…* y elige el zip.

El panel está en la vista 3D, barra lateral (`N`), pestaña **SL Rigger**. Menú radial: **Mayús+Alt+Q**.
Los exportadores también están en *Archivo → Exportar*.

## Novedades de la 0.4

* **Esqueleto oficial completo**: los 133 huesos (26 base + 107 Bento) y los 26 volúmenes de
  colisión, con las posiciones exactas del `avatar_skeleton.xml` del visor.
* **Bento por grupos**: el rig siempre lleva todos los huesos (para que funcione cualquier
  animación Bento) y tú eliges qué grupos deforman: manos, cara, orejas, cola, alas, patas
  traseras, ingle, columna y *fitted mesh*. Cada grupo tiene su color.
* **Fitted mesh**: los volúmenes (`BELLY`, `BUTT`, `CHEST`, `LEFT_PEC`…) se exportan con su
  rotación y escala oficiales, como necesita SL.
* **Límite de 110 articulaciones por malla** (el del visor): el exportador solo lista los huesos
  usados y sus padres, y la validación avisa si una malla se pasa.
* **Auto-rig en un clic**: preset → esqueleto → ajuste → pesos → limpieza → validación.
* **Transferir pesos del cuerpo a la ropa**, **simetrizar pesos** y **rig rígido** para robots.
* **Monitor HUD** en el visor 3D con estado en vivo y **mapa de calor de pesos**
  (rojo: sin peso, verde: correcto, magenta: más de 4 huesos).
* Interfaz nueva con tablero de estado, secciones plegables y menú radial.
* Batería de pruebas automáticas (`tests/test_addon.py`).

## Presets de avatar

En el desplegable sobre **Crear esqueleto SL** eliges las proporciones de partida:

| Preset | Altura aprox. | Notas |
|---|---|---|
| Humano estándar | 1,9 m | Igual que el esqueleto de SL |
| Petite | 1,5 m | Adulto pequeño |
| Gigante | 3 m | Hombros algo más anchos |
| Titán / kaiju | 4,5 m | Torso y hombros masivos |
| Musculoso | 2,1 m | Espalda ancha, cuello corto |
| Tiny | 0,7 m | Cabeza grande, extremidades cortas, cola y orejas |
| Furro antropomorfo | 1,9 m | Hocico, cuello algo más largo, cola y orejas |
| Furro digitígrado | 1,8 m | Patas de animal (tobillo elevado, pie largo), cola y orejas |
| Kemono / chibi furro | 1,4 m | Estilo anime, cabeza grande, cola y orejas |

Todo preset distinto de *Humano estándar* necesita subirse con **Include joint positions**.
Los presets de furro activan la deformación de la cola y las orejas. Cualquier grupo Bento se
puede activar o desactivar después en *Esqueleto Bento → Grupos que deforman*.

## Flujo: malla → avatar o ropa rigged

1. **Crear esqueleto SL**: crea el esqueleto oficial completo (Bento y volúmenes). En el panel
   *Ajustar última operación* eliges qué grupos deforman. Mira hacia −Y (vista frontal de Blender).
2. **Ajustar esqueleto a la malla** (opcional): selecciona las mallas y el esqueleto
   (el esqueleto como objeto activo). Se escala y se centra según la altura de la malla.
   Después aplica la escala (`Ctrl+A → Escala`) y, al subir el modelo a SL, marca
   *Incluir posiciones de articulaciones*.
3. Si la malla ya venía con rig de **Mixamo, Unreal o Rigify**, usa
   **Convertir grupos a nombres SL**: renombra y fusiona los grupos de vértices.
4. **Vincular al esqueleto** (mallas seleccionadas y el esqueleto activo):
   * *Pesos auto*: calcula pesos automáticos y los limpia para SL.
   * *Conservar*: mantiene los grupos que ya existen (después de convertir).
   * *Vacíos*: crea grupos vacíos para pintar los pesos a mano.
5. **Limpiar pesos para SL**: deja como máximo 4 huesos por vértice, borra pesos
   ínfimos y normaliza.
6. **Validar** y **Exportar .dae**.

En el subidor de Second Life, en la pestaña *Upload options*, marca **Include skin weight**
y, si moviste o escalaste huesos, **Include joint positions**.

## Flujo: objeto estático

1. **Preparar objeto**: aplica la rotación y la escala y centra el origen.
2. **Generar LODs**: crea copias decimadas (`_MED`, `_LOW`, `_LOWEST`) en una
   colección `SL_LOD_<nombre>`. Puedes cambiar el ratio del modificador *SL_Decimate*.
3. **Generar física**: crea una envolvente convexa `_PHYS`.
4. **Exportar .dae**: escribe `modelo.dae` y, si existen, `modelo_MED.dae`, `modelo_LOW.dae`,
   `modelo_LOWEST.dae` y `modelo_PHYS.dae`. En el subidor, carga cada uno en su nivel de LOD o de física.

## glTF y materiales PBR

**Exportar glTF para SL** usa el exportador glTF de Blender con los ajustes que pide SL:
eje Y arriba, sin animaciones, sin morphs, sin compresión Draco ni WebP, máximo 4 influencias
por vértice y pose de reposo. Exporta también los LODs y la física igual que con `.dae`.

* En el subidor (*Build → Upload → Model*) carga el `.glb`. De momento SL solo toma el
  **color base** del modelo; no marques subir texturas.
* El glTF **rigged es experimental** en SL. Si el subidor falla, usa `.dae` para avatares y ropa.

**Exportar materiales PBR** escribe un `.glb` por cada material de las mallas seleccionadas.
Usa un *Principled BSDF* con texturas conectadas a *Base Color*, *Metallic*, *Roughness*,
*Normal* y *Emission*; el exportador empaqueta metal y rugosidad en un solo PNG como pide glTF.
En SL: *Build → Upload → Material* (solo en regiones con PBR) y luego aplica el material al objeto.

## Comprobaciones de la validación

* Máximo 8 materiales por objeto.
* Aviso a partir de 21 844 triángulos o 65 534 vértices por material (SL divide la cara).
* Texturas de más de 2048 px o que no son potencia de 2 (SL las reescala).
* Materiales sin caras y falta de mapa UV.
* Tamaño máximo de 64 m por eje y escala sin aplicar.
* Rigged: vértices sin peso, más de 4 influencias, grupos que no son huesos SL
  y huesos que faltan en el rig.

## Detalles del exportador rigged

* Convierte la geometría de los ejes de Blender (frente −Y) a los de SL (frente +X).
* Las articulaciones se exportan solo con traslación, como el esqueleto de SL, y la
  matriz inversa de bind es la traslación inversa de cada articulación.
* Se conservan las 4 influencias mayores de cada vértice. Los vértices sin peso se
  asignan a `mPelvis` y se avisa.
* La geometría se lee en la pose de reposo y se aplican los modificadores, salvo el armature.

## Limitaciones de esta versión (0.4 beta)

* No se ha probado todavía subiendo a Second Life: necesita pruebas en Aditi u OpenSim.
* La edición Founder se ha revisado contra la API de Blender 3.5 pero solo se ha ejecutado en 4.2.
* No exporta animaciones (`.anim` o `.bvh`) ni importa formas (shapes) de SL.
* Las proporciones de los presets son un punto de partida.
