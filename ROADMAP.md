# Hoja de ruta de SL Rigger

Lista de todo lo que queda por añadir. Se marca cada punto al terminarlo.

Estado actual (0.2): esqueleto base con dedos Bento, conversión de Mixamo, Unreal y Rigify,
vinculación y limpieza de pesos, LODs y física, validación, exportación a `.dae`, glTF y
materiales PBR.

---

## 1. Esqueleto y rigging

- [ ] Leer las posiciones exactas del `avatar_skeleton.xml` oficial (en lugar de valores aproximados).
- [ ] Esqueleto Bento completo: cara (unos 50 huesos), alas, cola, patas traseras y los huesos `mSpine1–4`.
- [ ] Volúmenes de colisión para *fitted mesh* (`PELVIS`, `BELLY`, `BUTT`, `CHEST`, `LEFT_PEC`, `UPPER_BACK`, `LOWER_BACK`, `L_UPPER_ARM`…).
- [ ] Puntos de anclaje (*attachment points*: `Chest`, `Spine`, `Avatar Center`, `Left Hand`…) con sus posiciones reales.
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

- [ ] Copiar pesos de un cuerpo de referencia a la ropa (transferencia por proximidad o por superficie), imprescindible para kits de desarrollo.
- [ ] Simetrizar pesos de izquierda a derecha y viceversa.
- [ ] Suavizar pesos solo en zonas seleccionadas, sin pasar de 4 influencias.
- [ ] Copiar pesos de los volúmenes de colisión (*fitted*) de forma proporcional a los huesos `m*`.
- [ ] Preajustes de pesos por zona (cuello, hombros, caderas) para corregir los problemas típicos.
- [ ] Mapa de calor de influencias por vértice (verde con 1–4 influencias, rojo con más de 4 o sin peso).

## 4. Ropa y cuerpos de malla

- [ ] Importar `.dae` de SL y kits de desarrollo (Maitreya, Legacy, Reborn, eBody, Belleza…; licencia de cada creador).
- [ ] Generar tallas (XXS–XL) a partir de una prenda, con desplazamiento por volumen.
- [ ] Ajuste automático de la prenda al cuerpo (evitar que el cuerpo atraviese la ropa) con distancia mínima configurable.
- [ ] Dividir el cuerpo en zonas de alfa (*alpha cuts* o caras para el HUD de alfas) a partir de materiales o selecciones.
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
- [ ] Física avanzada: cajas automáticas para edificios, descomposición convexa y física por pieza.
- [ ] Exportar varios objetos como *linkset* con nombres y orden de enlazado.
- [ ] Control del pivote y del origen pensando en cómo se rotan y editan los objetos en SL.

## 7. Animesh y complejidad

- [ ] Modo animesh (objetos animados): validar sus límites y exportar malla y animaciones juntas.
- [ ] Estimar la complejidad del avatar (ARC) de una prenda o un avatar completo.

## 8. Animaciones

- [ ] Exportar a `.anim` (formato nativo: prioridad por articulación, bucle, *ease in/out*, huesos Bento, traslaciones).
- [ ] Exportar a `.bvh`.
- [ ] Pasar animaciones de Mixamo (y de otros rigs) al esqueleto SL.
- [ ] Biblioteca de poses de mano y de expresiones faciales Bento.
- [ ] Cargar animaciones estándar de SL (estar de pie, andar, sentarse) para probar cómo deforma la ropa.
- [ ] Animaciones con traslación de cadera y de articulaciones, y con prioridades por hueso.

## 9. Exportación y flujo de trabajo

- [ ] Exportación por lotes: varios objetos o tallas a varios archivos de una vez.
- [ ] Preajustes de exportación guardables (por proyecto o por tipo de prenda).
- [ ] Nombres de archivo automáticos con versión (`prenda_v03_M.dae`).
- [ ] Perfiles por red: Second Life (red principal y Aditi) y OpenSim, con sus límites.
- [ ] Informe previo a la subida exportable (texto o HTML) con todos los avisos.
- [ ] Importar copias de seguridad de Firestorm (`.oxp` o `.dae`) para recuperar trabajo.

## 10. Calidad del plugin

- [ ] Pruebas automáticas (ejecutando `bpy` sin interfaz) para cada función.
- [ ] Probar en Blender 3.6, 4.2 LTS y 5.x.
- [ ] Interfaz en español e inglés.
- [ ] Validación real con el visor en Aditi u OpenSim, a partir de los registros del subidor.
- [ ] Documentación con capturas y vídeos cortos de cada flujo.
