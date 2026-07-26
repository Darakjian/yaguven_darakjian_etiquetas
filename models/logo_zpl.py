"""Wordmark "DARAKJIAN" del logo de la compania, ya rasterizado a ZPL.

Pre-convertido para no depender de PIL ni de leer res.company en cada impresion.
Regenerar si cambia el logo: bajar el PNG de `res.company.logo` y componerlo
sobre fondo BLANCO (es RGBA y la termica no imprime transparencia).

COMO SE AISLA EL WORDMARK (lo que costo dos intentos): el subtitulo "JEWELERS"
NO se separa cortando a una altura fija, porque **se solapa verticalmente** con
el wordmark -- en el PNG de 640x118 el wordmark ocupa y=12..93 y el subtitulo
y=85..105. Cortar por porcentaje se come el descendente de la "J" y la marca
sale partida abajo. Tampoco alcanza con blanquear "de tal fila para abajo" a la
derecha: esa franja todavia contiene las letras finales del wordmark. El
criterio correcto:
  1. filas donde hay tinta SOLO a la derecha -> ahi vive el subtitulo puro
     (y=94..105), y de ahi sale la x donde arranca (x=438);
  2. blanquear el rectangulo x>=438, y>=85 -- el 85 es donde el subtitulo
     empieza a solaparse con el descendente de la J;
  3. recien entonces sacar el bbox -> wordmark aislado 619x82.

Se descarta el subtitulo porque a la altura que entra en esta etiqueta cae a
~3 dots y es ilegible: es el DPI de la impresora (203), no la resolucion del
archivo (el logo de darakjian.com es el mismo PNG de 640x118).

Medidas: 100x13 dots @203dpi. Antes eran 150x19, cuando el wordmark ocupaba
una linea entera abajo a la derecha; con el layout en bandas pasa a la banda
superior, al lado del SKU y del precio, y a ese tamano sigue legible.
"""

LOGO_W = 100
LOGO_H = 13
LOGO_ZPL = "^GFA,169,169,13,7F00C07F00201C70E70180E06061C0C06180701840C301C070606061E06180701880C303C078606063606180D81900C302E05C606062307700981F00C306604E606063F06301FC1D80C307F0476060641861010C18C0C30C3043A060C41861830618E0C3083041E0618C1C60E2071870C31818C0E0761C0C7036071C1CC7181CC0600000000000000000C0000000000000000000000000800000000000000000000000010000000000"
