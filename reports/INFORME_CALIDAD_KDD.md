# Informe de Calidad KDD - Lote 202611
 
## 1. Metricas de calidad (ISO/IEC 25012)
 
| Metrica | Valor |
|---|---|
| Completitud (lote verificado, antes de limpiar) | 95.00% |
| Completitud (dataset limpio) | 100.00% |
| Integridad criptografica | 66.67% (2 archivos validados, 1 rechazados) |
| Unicidad de id_transaccion | 100.00% |
| Validez (registros limpios / verificados) | 87.00% (87 de 100) |
 
## 2. Distribucion de importe_eur (tras la limpieza)
 
| Estadistico | Valor (EUR) |
|---|---|
| Media | 70.99 |
| Mediana | 73.44 |
| Desviacion estandar | 26.34 |
| Percentil 25 | 53.80 |
| Percentil 75 | 85.34 |
 
## 3. Registros en cuarentena
 
| Motivo | Registros |
|---|---|
| nulo_en_columna_obligatoria | 3 |
| outlier_importe | 3 |
| importe_no_positivo | 2 |
| unidades_menores_a_1 | 2 |
| timestamp_invalido | 1 |
| fecha_futura | 1 |
| fecha_fuera_del_anio_en_curso | 1 |
 
Total en `quarantine/bad_records.csv`: 13.
 
## 4. Conclusiones tecnicas
 
- Integridad: el fichero 'transacciones_tienda_sur.csv' se ha aislado en `quarantine/tampered/` por tener un valor hash invalido.
- Descartes: se descartaron los registros sin `id_transaccion` o sin `importe_eur`, porque son variables obligatorias que no se pueden tratar sin ellas.
- Coherencia: se rechazaron timestamps invalidos, fechas futuras o de otro año, importes <= 0 y unidades < 1, por no tener sentido de negocio.
- Outliers: se detectaron con la regla del IQR (1,5 x IQR) y se enviaron a cuarentena en lugar de borrarse, para poder gestionarlos.
- Imputacion: los nulos en `categoria` y `metodo_pago` se imputaron con "Desconocido", ya que son categoricas y la mediana no se aplica; de esa forma se pierde el registro.
- Resultado: el dataset limpio tiene 100% de completitud y una distribucion sin valores extremos, lo que garantiza la consistencia de los datos.
