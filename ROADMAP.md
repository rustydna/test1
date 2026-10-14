# Hoja de ruta de SL Rigger

Lista de todo lo que queda por añadir. Se marca cada punto al terminarlo.

Estado actual (0.5 beta): exportador .anim, biblioteca de poses y animaciones, retarget, anclajes, ropa, materiales PBR, certificado e interfaz nueva. Antes (0.4): esqueleto oficial Bento completo con fitted mesh, límite de 110 articulaciones, auto-rig en un clic, transferencia y simetría de pesos, rig rígido, monitor HUD, dos ediciones (Founder 3.5+ y Standard 4.2+). Antes: esqueleto base con dedos Bento, presets de avatar (gigantes, tinies, furros) con cola y orejas, conversión de Mixamo, Unreal y Rigify,
vinculación y limpieza de pesos, LODs y física, validación, exportación a `.dae`, glTF y
materiales PBR.

---

## 1. Esqueleto y rigging

- [x] Leer las posiciones exactas del `avatar_skeleton.xml` oficial (en lugar de valores aproximados).
- [x] Esqueleto Bento completo: cara (unos 50 huesos), alas, cola, patas traseras y los huesos `mSpine1–4`.
- [x] Volúmenes de colisión para *fitted mesh* (`PELVIS`, `BELLY`, `BUTT`, `CHEST`, `LEFT_PEC`, `UPPER_BACK`, `LOWER_BACK`, `L_UPPER_ARM`…).
- [x] Puntos de anclaje (*attachment points*: `Chest`, `Spine`, `Avatar Center`, `Left Hand`…) con sus posiciones reales.
- [ ] Rig de control para animar (IK y FK, controles de mano y de cara) sobre los huesos `m*`.
- [ ] Distinguir entre forma neutra y forma por defecto al vincular (fuente clásica de deformaciones).
- [ ] Ajuste del rig a la malla por huesos (brazos, piernas, cabeza), no solo por escala uniforme.
- [ ] Mantener un rig compatible al cambiar de versión de Blender (3.6 → 5.x).

## 2. Formas del avatar (*shapes*)

- [ ] Importar una forma de SL en XML (*Exportar forma* de Firestorm) y aplicar sus deslizadores al rig.
- [ ] Previsualizar en Blender cómo deforman los deslizadores de forma la ropa *fitted mesh*.
- [ ] Biblioteca de formas de prueba (bajita, alta, delgada, corpulenta) para comprobar la ropa con un clic.
- [ ] Exportar un *deformer*: una animación `.anim` con desplazamientos de articulaciones para cambiar proporciones.

## 3. Pesos

- [x] Copiar pesos de un cuerpo de referencia a la ropa (transferencia por proximidad o por superficie), imprescindible para kits de desarrollo.
- [x] Simetrizar pesos de izquierda a derecha y viceversa.
- [ ] Suavizar pesos solo en zonas seleccionadas, sin pasar de 4 influencias.
- [ ] Copiar pesos de los volúmenes de colisión (*fitted*) de forma proporcional a los huesos `m*`.
- [ ] Preajustes de pesos por zona (cuello, hombros, caderas) para corregir los problemas típicos.
- [x] Mapa de calor de influencias por vértice (verde con 1–4 influencias, rojo con más de 4 o sin peso).

## 4. Ropa y cuerpos de malla

- [ ] Importar `.dae` de SL y kits de desarrollo (Maitreya, Legacy, Reborn, eBody, Belleza…; licencia de cada creador).
- [x] Generar tallas (XXS–XL) a partir de una prenda, con desplazamiento por volumen.
- [x] Ajuste automático de la prenda al cuerpo (evitar que el cuerpo atraviese la ropa) con distancia mínima configurable.
- [x] Dividir el cuerpo en zonas de alfa (*alpha cuts* o caras para el HUD de alfas) a partir de materiales o selecciones.
- [ ] Soldar normales entre piezas separadas (cuello entre cabeza y cuerpo, muñecas y tobillos) para que no se vea la costura.

## 5. Bakes on Mesh (BOM) y texturas

- [ ] Asignar canales BOM a materiales (`BAKED_HEAD`, `BAKED_UPPER`, `BAKED_LOWER`, `BAKED_EYES`, `BAKED_SKIRT`, `BAKED_HAIR`, `LEFT_ARM`, `LEFT_LEG`, `AUX1–3`).
- [ ] Plantillas de UV del avatar del sistema para pintar o hornear piel y tatuajes.
- [ ] Hornear materiales complejos de Blender a texturas PBR compatibles con SL.
- [ ] Atlas de texturas: juntar varias texturas en una de 1024 o 2048.
- [ ] Exportar materiales clásicos (difuso, especular y normal) además de PBR.
- [ ] Modos de alfa (mezcla, máscara, emisivo) y doble cara en los materiales PBR.
- [ ] Estimar el uso de memoria de texturas.

## 6. Objetos estáticos y Land Impact

- [ ] Calcular aproximadamente el *Land Impact* (peso de descarga, física y servidor) antes de subir.
- [ ] LODs de mejor calidad: conservar bordes, UVs y todos los materiales en cada nivel.
- [x] Física avanzada: cajas automáticas para edificios, descomposición convexa y física por pieza.
- [ ] Exportar varios objetos como *linkset* con nombres y orden de enlazado.
- [ ] Control del pivote y del origen pensando en cómo se rotan y editan los objetos en SL.

## 7. Animesh y complejidad

- [ ] Modo animesh (objetos animados): validar sus límites y exportar malla y animaciones juntas.
- [ ] Estimar la complejidad del avatar (ARC) de una prenda o un avatar completo.

## 8. Animaciones

- [x] Exportar a `.anim` (formato nativo: prioridad por articulación, bucle, *ease in/out*, huesos Bento, traslaciones).
- [ ] Exportar a `.bvh`.
- [x] Pasar animaciones de Mixamo (y de otros rigs) al esqueleto SL.
- [x] Biblioteca de poses de mano y de expresiones faciales Bento.
- [ ] Cargar animaciones estándar de SL (estar de pie, andar, sentarse) para probar cómo deforma la ropa.
- [ ] Animaciones con traslación de cadera y de articulaciones, y con prioridades por hueso.

## 8b. Avatares no humanos y de tamaño especial

- [x] Presets de proporciones: petite, gigante, titán, musculoso, tiny, furro, digitígrado, kemono.
- [ ] Taur y centauro: cuerpo trasero con los huesos `mHindLimb1–4` y pesos preconfigurados.
- [ ] Naga y sirena: cola larga como parte inferior del cuerpo con `mTail1–6` y las piernas recogidas.
- [ ] Alas Bento (`mWing1–4` y `mWing4Fan`) con presets: pájaro, dragón, murciélago y hada.
- [ ] Cuadrúpedos (*feral*): lobo, felino o caballo sobre el esqueleto SL, con animaciones de andar.
- [ ] Hocicos Bento: presets de cara para perro, gato, zorro, lobo y dragón (mandíbula, labios, nariz).
- [ ] Orejas largas (conejo), cuernos y crestas.
- [ ] Manos de 3 o 4 dedos y zarpas (fusionando pesos de dedos).
- [x] Robots y mechas: pesos rígidos (1 hueso por pieza) con un clic.
- [x] Animaciones procedurales: cola que se mueve, orejas que se agitan, respiración e *idle* furro.
- [ ] Pelo y peluche: tarjetas de pelo con alfa, peluche en capas y aviso del coste en complejidad.
- [x] Editor de presets: guardar las proporciones de un rig como preset propio y compartirlo (JSON).
- [ ] Aviso de escala: comprobar los límites de desplazamiento de articulaciones y la altura de la cámara.

## 9. Exportación y flujo de trabajo

- [x] Exportación por lotes: varios objetos o tallas a varios archivos de una vez.
- [ ] Preajustes de exportación guardables (por proyecto o por tipo de prenda).
- [ ] Nombres de archivo automáticos con versión (`prenda_v03_M.dae`).
- [ ] Perfiles por red: Second Life (red principal y Aditi) y OpenSim, con sus límites.
- [x] Informe previo a la subida exportable (texto o HTML) con todos los avisos.
- [ ] Importar copias de seguridad de Firestorm (`.oxp` o `.dae`) para recuperar trabajo.

## 10. Calidad del plugin

- [x] Preferencias del add-on: tema de color del HUD, atajo configurable, idioma.
- [x] Guardar y cargar presets propios (JSON) desde un rig ajustado.

- [x] Pruebas automáticas (ejecutando `bpy` sin interfaz) para cada función.
- [ ] Probar en Blender 3.6, 4.2 LTS y 5.x.
- [ ] Interfaz en español e inglés.
- [ ] Validación real con el visor en Aditi u OpenSim, a partir de los registros del subidor.
- [ ] Documentación con capturas y vídeos cortos de cada flujo.
