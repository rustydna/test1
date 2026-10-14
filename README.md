# SL Rigger para Blender

Add-on de Blender (en la línea de Avastar o Bento Buddy) para convertir mallas 3D en
**avatares y ropa rigged** y en **objetos estáticos** listos para subir a **Second Life**.

Formatos de exportación:

* **Collada `.dae`**: exportador propio (Blender ya no trae el suyo). Es el formato
  recomendado para avatares y ropa rigged.
* **glTF `.glb` / `.gltf`**: lo acepta el subidor de modelos de SL desde el visor 2025.05
  (también Firestorm). Recomendado para objetos estáticos.
* **Materiales PBR `.glb`**: un archivo por material para *Build → Upload → Material*.

## Instalación

1. Comprime la carpeta `sl_rigger` en un `.zip` (por ejemplo `zip -r sl_rigger.zip sl_rigger`).
2. En Blender: *Editar → Preferencias → Complementos → Instalar desde disco…* y elige el zip.
   * Blender 4.2 o superior lo instala como extensión (`blender_manifest.toml`).
   * Blender 3.6–4.1 lo instala como complemento clásico (`bl_info`).
3. El panel aparece en la vista 3D, en la barra lateral (`N`), pestaña **SL Rigger**.
   Los exportadores también están en *Archivo → Exportar*.

## Flujo: malla → avatar o ropa rigged

1. **Crear esqueleto SL**: crea un armature con los 26 huesos base de Second Life y,
   si lo activas, los 30 huesos Bento de los dedos. Mira hacia −Y (vista frontal de Blender).
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

## Limitaciones de esta versión (0.2)

* Huesos Bento incluidos: solo las manos. Faltan la cara, las alas, la cola y las
  extremidades traseras.
* No hay volúmenes de colisión (`PELVIS`, `BELLY`… para el *fitted mesh*).
* No exporta animaciones (`.anim` o `.bvh`).
* Las posiciones de los dedos Bento son aproximadas. Comprueba el resultado en el
  visor (o en Aditi, la red beta, que es gratis) antes de subirlo en la red principal.
