# HANDOFF — Foso de los Desterrados / mazmorra-perrera para Second Life

**Fecha:** 14 de octubre de 2026.
**Estado de esta entrega:** versión visual V1 aprobada por el usuario; corrección de colisiones y contactos pendiente.
**Finalidad:** permitir a otra IA continuar el proyecto, reproducir el trabajo y compararlo con propuestas alternativas sin perder los requisitos.

> Texto original del handoff de la V1. Traducción al inglés en `HANDOFF_EN.md`. Los cambios de la V2 están en `V2_CAMBIOS.md`.

## 1. Lo que quiere el usuario ahora

Un edificio de fantasía medieval oscura, inspirado en el ambiente de Juego de Tronos: una mazmorra/perrera de celdas grandes, con arquitectura convincente, barrotes, portones pesados, cadenas y herrajes realmente modelados. Es un entorno de roleplay consentido entre amigos en **Second Life**.

La versión actual le gusta: ha dicho «me encanta, se ve genial». **No hay que rediseñarla desde cero ni cambiar su lenguaje arquitectónico sin motivo.** Quiere mejorar fallos de física al caminar o entrar en las celdas, y algunas anillas y piezas que parecen flotar.

Su petición inmediata es este handoff detallado para comparar el trabajo de otras IAs. Después autoriza continuar las correcciones.

### Restricciones vigentes, por orden de importancia

1. **Sin texturas.** El usuario quiere aplicar las suyas. Entregar geometría y UVs utilizables; materiales grises neutros están bien.
2. **Barrotes, cadenas, anillas y herrajes en geometría 3D.** No sustituirlos por imágenes con transparencia.
3. Estética sobria de mazmorra/perrera; evitar aspecto de juguete, bloques uniformes, decoración de castillo infantil o mobiliario desproporcionado.
4. **Presupuesto objetivo: 150 de land impact (LI) en Second Life.** Inicialmente eran unas 100, pero el usuario lo amplió a 150. El LI exacto sigue sin estar acreditado por el asistente en un visor.
5. Terreno total: **2.023 m²**. La construcción debe ocupar **como máximo la mitad: 1.011,5 m²**.
6. Mantener la distribución de ocho celdas que el usuario ha aprobado visualmente, salvo que una necesidad de optimización se justifique.
7. Las prendas, si se añaden, deben ser **exclusivamente masculinas**. Este requisito procede de una fase anterior y sigue aplicando a cualquier nuevo atrezzo textil.

## 2. Cómo evolucionó el encargo

- Petición inicial: perrera para perros gigantes, tipo dogo/dinosaurio de fantasía, con varias celdas, estética Juego de Tronos y texturas.
- Se preguntó por el uso; al principio el usuario seleccionó construcción real. Después aclaró el contexto de rol y finalmente concretó la plataforma **Second Life**. El alcance operativo actual es el activo digital para SL.
- Quería austeridad, paja, barro aparente, abandono y prendas masculinas desechadas.
- Se produjo una primera maqueta texturizada, con ocho recintos de 4 × 7 m. No es la versión aprobada que debe continuarse.
- Al aparecer el límite de 100 LI, se ensayó una variante de 96 prims nativos, con detalle trasladado a texturas y un constructor LSL. **Este enfoque quedó descartado.** No usar sus scripts ni sus texturas como base del trabajo actual.
- El usuario rechazó el aspecto visual anterior, calificándolo de Playmobil. Ordenó expresamente: **quitar texturas, entregar UVs y rehacer la malla con un aspecto más serio**.
- Amplió el presupuesto a 150 LI e indicó los 2.023 m² de terreno y el máximo de media parcela.
- Se rehízo el conjunto como arquitectura de arcadas y bóvedas, con barrotes y cadenas 3D, y presentación a escala humana. Esta es la versión que aprobó.

**No recuperar las decisiones de la variante de 96 prims.** Las 65 piezas mesh actuales tampoco equivalen a 65 LI.

## 3. Entrega aprobada y archivos principales

La carpeta de trabajo vigente es **`outputs/Foso_Mazmorra_UV_150/`**.

| Archivo | Uso |
|---|---|
| `Foso_Mazmorra_UV_150.blend` | Fuente editable, con HIGH, LODs, física, cámaras y luces |
| `Foso_HIGH.dae` | Modelo visual principal para importar |
| `Foso_MEDIUM.dae` | Nivel medio |
| `Foso_LOW.dae` | Nivel bajo |
| `Foso_LOWEST.dae` | Nivel mínimo |
| `Foso_PHYS.dae` | Proxies de colisión |
| `UV_layouts/*.svg` | 65 plantillas UV del HIGH |
| `01_Patio_sin_texturas.png` | Perspectiva principal aprobada |
| `02_Detalle_cadenas.png` | Detalle con luz de relleno para leer eslabones y herrajes |
| `03_Vista_distribucion.png` | Vista general con bóvedas retiradas |
| `04_Planta_medidas.png` | Planta de implantación |
| `LEEME.md` | Guía de uso |
| `Verificacion.json` | Recuento y restricciones verificadas localmente |
| `QA_exportacion.json` | Informe de exportación por pieza y nivel |

El archivo `Foso_Mazmorra_UV_150.zip` contiene la entrega aprobada. En el paquete de handoff se incluye una copia de esa entrega y los scripts necesarios para estudiarla.

En la carpeta original pueden existir renders antiguos con nombres parecidos, como `03_Distribucion.png`, `04_Planta_672m2.png` o `02_Barrotes_y_cadenas.png`. **Los nombres de la tabla identifican las vistas finales.**

## 4. Dimensiones y organización

- Unidades Blender y COLLADA: **metros, escala 1:1, Z vertical**.
- Huella exterior de la base: **24 × 28 m = 672 m²**.
- Esto supone aproximadamente **33,22 %** de la parcela de 2.023 m² y queda por debajo del límite de 1.011,5 m².
- La parcela solo se conoce por superficie; no se dispone de la forma de sus linderos. El usuario debe poder orientar o colocar el rectángulo de 24 × 28 m en su parcela.
- Ocho celdas, en dos alas de cuatro.
- Dimensión nominal de cada celda: **5 × 8 m**, 40 m² antes de descontar detalles interiores.
- Corredor central libre nominal: **4,8 m**.
- Paso longitudinal entre ejes de celdas: **5,3 m**.
- Cada frente tiene una arcada apuntada con hueco total de unos 3,6 m de ancho; la hoja practicable central es de unos **1,4 × 2,6 m**, con rejas fijas a los lados y encima.
- Bóvedas individuales retirables para trabajar o visualizar interiores.
- Entrada monumental con dos hojas de hierro independientes y frontón, sin almenas de juguete.
- Cota superior del frontón: aproximadamente **6,85 m** sobre cero. La cimentación/base baja 0,38 m bajo cero; envolvente vertical total aproximada de 7,23 m.

## 5. Qué está modelado y qué no

### Sí está modelado

- Muros continuos y macizos, divisiones y plataformas bajas al fondo de las celdas.
- Arcadas apuntadas con jambas, dos órdenes de molduras/revelados y piezas de dovela geométricas.
- Ocho conjuntos de reja fija y ocho hojas de celda independientes.
- Dos hojas de portón de entrada y dos rejas del antepatio.
- Barrotes volumétricos, travesaños, cerrojos sencillos, bisagras y tiradores/anillas.
- Ocho cadenas colgantes, con eslabones alternados en planos perpendiculares, argolla y placa de anclaje.
- Bóvedas, pavimento central con losas geométricas y tablillas dispersas.

### No está incluido en esta versión

- Texturas, imágenes, mapas PBR, materiales procedurales o rejas con alpha.
- Perros/personajes acabados, rigging o animaciones.
- Scripts operativos de puertas en SL.
- Simulación dinámica de cadenas, prendas o cuerpos.
- Prendas masculinas ni paja detallada como malla en esta revisión UV. La preferencia anterior se conserva como contexto si se amplía el atrezzo, pero no hay que afirmar que ya esté implementada.
- Un proyecto constructivo físico, cálculos estructurales o instalaciones.

## 6. Organización del Blender

Colecciones principales:

- **`MALLA | HIGH - editar y texturizar`**: modelo principal.
- **`LOD | MEDIUM`**, **`LOD | LOW`**, **`LOD | LOWEST`**: versiones de menor detalle, ocultas en la vista principal.
- **`FISICA | simplificada`**: proxies, también ocultos.
- Colecciones **PRESENTACION**: cámaras, luces y rótulos. No exportarlas como parte del activo.
- Dentro de HIGH hay subcolecciones de bóvedas y muros cercanos para facilitar secciones y vistas de trabajo.

Escenas:

1. `01 | Patio - arcadas y cadenas`: perspectiva a escala humana, vista principal.
2. `02 | Coupe - distribution`: distribución sin bóvedas.
3. `03 | Fer et chaines`: detalle de hierro/cadenas, con una luz de relleno propia.
4. `04 | Implantation 24 x 28 m`: planta con rótulos.

Parte de los nombres internos están en francés por decisiones del generador; no implican requisitos nuevos.

Las piezas llevan una propiedad **`sl_name`** que identifica su correspondencia entre HIGH, LODs y PHYS. No romperla ni reordenar caprichosamente los objetos al exportar.

Convención de piezas:

- `A00_Fondation`: base.
- `A01_Dallage_central`: pavimento central.
- `A02_Arcade_fond`: arcada del fondo.
- `A03_Portail_entree`, `A04_Fronton_entree`: entrada.
- Para cada celda `C01`–`C08`: `Murs_et_banquette`, `Arcade_pierre`, `Grille_fixe`, `Porte_pivot`, `Chaine_et_ancrage`, `Voute_amovible`, `Planches_au_sol`.
- `E1/E2_Porte_entree`, `E3/E4_Grille_avant`: entrada/antepatio.

## 7. Materiales y UVs

Los materiales de las piezas son categorías neutras: **piedra, suelo, hierro y madera**. Existe además un material claro utilizado por los rótulos de presentación.

- No hay imágenes de textura en el Blender ni referencias a archivos de imagen en los DAE.
- Cada pieza HIGH tiene su propio despliegue **UVMap 0–1**.
- El HIGH se desplegó con Smart Project, límite angular de 66°, separación de islas de 0,018 y ponderación de área de 0,5.
- Las 65 plantillas SVG describen los contornos de esas UVs, una por pieza. **No constituyen un atlas global de todo el edificio.**
- Los LODs finales se obtienen copiando HIGH y simplificando su geometría con Decimate, conservando sus datos UV.
- Se verificaron cero triángulos con UV colapsadas y cero coordenadas fuera de 0–1 en los cuatro niveles visuales.
- Si se cambian contactos de herrajes, conviene mover componentes existentes sin repaquetar sus UVs. Si se añade geometría, darle UVs coherentes y documentar el cambio.

## 8. Recuentos finales V1

| Nivel | Objetos mesh | Triángulos |
|---|---:|---:|
| HIGH | 65 | 44.704 |
| MEDIUM | 65 | 9.874 |
| LOW | 65 | 4.980 |
| LOWEST | 65 | 4.288 |
| PHYS | 65 | 1.664 |

Son cifras de geometría, **no resultados de land impact**. La silueta de cada LOD visual se ajustó a la misma caja delimitadora del HIGH, evitando desplazamientos o cambios de escala causados por Decimate.

## 9. Exportación COLLADA y trampas ya resueltas

Blender instalado: **5.2.1 LTS**, con Cycles y una NVIDIA RTX 5090 disponible. La exportación COLLADA se resolvió mediante un exportador Python propio porque esta instalación no ofrece el exportador DAE antiguo.

`work/export_collada_sl.py` proporciona:

`export_collada(objects, filepath, mode='HIGH')`

- COLLADA **1.4.1**, unidad metro, `Z_UP`.
- Posiciones por vértice; normales divididas y UVs por loop/esquina, preservando seams y aristas duras.
- Índices `VERTEX`, `NORMAL`, `TEXCOORD` separados por triángulo.
- Materiales Lambert grises, sin imágenes.
- Modificadores deben estar aplicados antes de exportar.
- Correspondencia por `sl_name`; añade los sufijos `_LOD2`, `_LOD1`, `_LOD0` y `_PHYS` en los niveles correspondientes.
- Las matrices COLLADA se serializan por filas. No transponerlas por confundirlo con la convención matemática de vectores columna.
- **Problema real corregido:** objetos PHYS en colecciones excluidas podían tener `matrix_world` sin actualizar, exportándose desplazados 8–21 m. En objetos sin padre ni constraints, el exportador usa una copia de **`matrix_basis`**, que conserva la transformación local correcta. Con padre/constraints utiliza `matrix_world`.
- También se actualizó el depsgraph antes de excluir niveles.

El exportador pasó **12 pruebas** locales, incluyendo matrices no identidad, jerarquías/constraints, UV seams, normales duras, materiales, nombres de LOD y caché de física oculta.

## 10. Validación efectuada y sus límites

Comprobado localmente en los archivos:

- Los cinco DAE son XML válido y tienen índices válidos.
- 65 objetos por nivel, nombres y materiales correspondientes.
- Cero imágenes o texturas referenciadas.
- Cero triángulos geométricos degenerados en los niveles visuales.
- UVs visuales dentro de 0–1 y sin colapsos.
- AABB visuales coincidentes exactamente con HIGH.
- PHYS situado correctamente después de corregir las matrices.
- Huella exterior real de 24 × 28 m.
- El ZIP final se abrió y pasó la comprobación de integridad.

**Esto no acredita colisiones correctas dentro de Second Life.** El usuario ya ha informado de fallos allí al caminar o entrar en las celdas. No se dispone todavía del detalle exacto de su configuración de importación, Physics Shape Type, uso de Analyze o escala aplicada.

Tampoco se ha registrado un valor real de LI desde su visor. No presentar «150 LI» como garantía ni «65 piezas» como coste de terreno.

## 11. Problemas pendientes, conocidos y prioritarios

### A. Colisiones en Second Life — reporte del usuario

Confirmado por el usuario: los fallos aparecen **en Second Life al caminar o entrar en las celdas**. Auditar el PHYS, su correspondencia con cada mesh, huecos reales, suelo, plataformas y geometría de las hojas. Revisar también las opciones del importador y el Physics Shape Type. No asumir que todos los problemas son de configuración ni afirmar que están arreglados solo porque el XML sea válido.

La física actual es simplificada. Las cadenas y tablillas son decorativas y pueden dejarse con física None cuando el conjunto esté montado; los marcos y muros sí deben permitir paso por las aberturas. No envolver todo el edificio en un único convex hull que cierre los interiores.

Las hojas cerradas bloquean el paso por diseño; como no hay scripts de apertura, comprobar si el usuario intenta atravesar una puerta todavía cerrada. Preguntarlo con precisión si hace falta, sin desestimar otros fallos.

### B. Herrajes y detalles flotantes — reporte y hallazgos preliminares

El usuario detecta algunas anillas y otras piezas sin apoyo aparente. Auditoría estática inicial del generador:

- Las placas de cadena están centradas en `y=ystart+0.28`, espesor 0,08 m: su trasera queda en +0,24, mientras el muro divisor llega a +0,15. **Hay unos 9 cm de separación.**
- Las argollas de los dos portones de entrada carecen de una grapa/placa que las conecte de manera visible a los barrotes; separación aproximada de 4,9 cm.
- La primera unión entre argolla de anclaje y eslabón presenta una separación mínima de unos 2,3 cm en una dirección: revisar la intersección 3D, no solo la proyección frontal.
- Las molduras de las arcadas laterales tienen aproximadamente 1 cm de separación de la piedra: revisar el centro X y la profundidad del perfil.

Estos son candidatos concretos para V2. Confirmarlos contra el Blender final antes de modificar; no mover todo un objeto si solo debe desplazarse un subcomponente.

### C. Otros puntos a conservar/revisar

- Las puertas tienen origen de bisagra en Blender, pero SL puede recentrar el mesh según su bounding box. **No prometer que un script de giro funcionará sin adaptar pivotes.**
- Los proxies de techo son cajas simplificadas: su diferencia respecto a la bóveda visual es deliberada, pero debe revisarse que no invadan el espacio del avatar.
- Evitar aumentar inútilmente geometría/LI para resolver una unión que puede arreglarse desplazando una placa o añadiendo una grapa pequeña.

## 12. Fuentes y reproducción

Scripts relevantes, incluidos en el paquete de handoff si están disponibles:

| Script | Función |
|---|---|
| `work/build_dungeon_uv.py` | Generación de arquitectura, HIGH/LODs/PHYS, UVs, escenas, renders y DAE |
| `work/export_collada_sl.py` | Exportación COLLADA propia |
| `work/fix_lod_bounds.py` | Igualar bounds visuales y reexportar/salvar la revisión final |
| `work/finish_dungeon.py` | Añadir luz de detalle, renderizar vistas finales y guardar |
| `work/audit_dungeon.py` | Auditoría de triángulos y UVs desde el Blender |
| `work/qa_collada_sl.py` | Auditoría de correspondencia, UVs, índices, bounds y transformaciones de DAE |

Los scripts calculan `outputs/` desde el directorio padre de `work/`. Para reproducir en otra máquina, conservar esa estructura y adaptar la ruta del ejecutable de Blender. El modelo entregado ya incorpora los pasos posteriores: no es necesario regenerarlo para empezar a corregir.

Orden de reconstrucción recomendado:

1. Ejecutar `build_dungeon_uv.py` con Blender en segundo plano; `-- --no-render` evita repetir imágenes.
2. Ejecutar `finish_dungeon.py` sobre el Blender generado si se necesitan las vistas finales. Esperar a que termine: guarda el archivo al final.
3. **Después**, ejecutar `fix_lod_bounds.py` sobre ese Blender para guardar/exportar los LODs finales alineados.
4. Auditar UVs, matrices, correspondencia y colisiones antes de empaquetar.

No ejecutar simultáneamente dos procesos que guarden el mismo `.blend`: se detectó y corrigió una carrera donde el proceso de render podía sobrescribir ajustes posteriores de LOD.

Fuentes técnicas primarias consultadas:

- [Importación de mesh en Second Life](https://community.secondlife.com/knowledgebase/english/uploading-a-mesh-model-r274/).
- [Cálculo de land impact](https://community.secondlife.com/knowledgebase/english/calculating-land-impact-r273/).
- [Name-based matching del importador](https://wiki.secondlife.com/wiki/Mesh_Import_test#Name_based_matching).
- [Especificación COLLADA 1.4.1](https://www.khronos.org/files/collada_spec_1_4.pdf).

## 13. Encargo listo para copiar a otra IA

> Continúa el proyecto adjunto de una mazmorra/perrera medieval para Second Life. La arquitectura de la versión UV ya está aprobada por el usuario: conserva sus ocho celdas, arcadas, barrotes, portones y cadenas. Debe seguir sin texturas, con UVs utilizables. El terreno total es de 2.023 m² y el conjunto no puede ocupar más de 1.011,5 m²; la base actual mide 24 × 28 m = 672 m². El presupuesto objetivo es 150 LI, todavía sin un valor real documentado desde el visor. El usuario ha encontrado problemas de física al caminar/entrar en celdas en Second Life y algunas anillas o detalles visualmente flotantes. Audita y corrige esos problemas sobre una copia V2 sin rediseñar la arquitectura aprobada. Empieza por placas de cadenas separadas unos 9 cm de los muros, conexión entre argolla y primer eslabón, anillas de portones sin grapa y molduras separadas de la piedra. Revisa el PHYS y las opciones de importación de SL, sin atribuir de antemano el fallo a una sola causa. Entrega Blender, DAE HIGH/MEDIUM/LOW/LOWEST/PHYS coherentes, UVs y una comparación concreta de cambios y pruebas. Distingue las comprobaciones locales de las pruebas reales en Second Life. Lee el handoff completo antes de actuar y mantén la V1 intacta como referencia.

## 14. Cómo comparar resultados entre IAs

Comparar sobre la misma V1 y el mismo presupuesto:

1. Calidad y proporción arquitectónica, conservando el estilo que ya gustó.
2. Contactos reales de placas, anillas, cadenas y herrajes, con primeros planos.
3. Entrada y circulación en SL con la física usada y ajustes documentados.
4. LI **medido en visor**, a escala 1:1, frente al objetivo de 150.
5. UVs útiles, sin colapsos y con LODs coherentes.
6. Exportación reproducible, archivos editables y ausencia de dependencias de texturas.
7. Evidencias de qué se comprobó, qué no, y qué coste visual o de rendimiento tuvo cada arreglo.

Este documento describe la **V1 aprobada antes de los arreglos nuevos**. Cualquier corrección posterior debe identificarse como V2 y acompañarse de su propio registro de cambios.
