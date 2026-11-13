from django.dispatch import Signal

# Se envía dentro de la transacción de confirmar(), con la venta ya cobrada.
# Argumentos: venta. Quien la escuche y falle deshace la venta entera.
venta_confirmada = Signal()
