# Wiring Servo dan LED untuk Raspberry Pi 4 Model B

## 1) Servo SG90 (2 unit)

Kedua servo dapat dipasang ke Raspberry Pi 4 Model B dengan pin PWM berikut:

- Servo 1 -> GPIO12 (BCM)
- Servo 2 -> GPIO19 (BCM)

### Wiring dasar
- Servo VCC -> 5V Raspberry Pi
- Servo GND -> GND Raspberry Pi
- Servo Signal 1 -> GPIO12
- Servo Signal 2 -> GPIO19

### Diagram ringkas
```text
Raspberry Pi 4 Model B
+-----------------------------+
|                             |
|  5V  -----> Servo VCC       |
|  GND -----> Servo GND       |
|  GPIO12 -> Servo 1 Signal   |
|  GPIO19 -> Servo 2 Signal   |
|                             |
+-----------------------------+
```

> Catatan: gunakan power supply 5V yang cukup stabil untuk servo, karena servo bisa menarik arus cukup besar. Jika perlu, gunakan eksternal 5V supply dan shared ground dengan Pi.

## 2) LED indikator

LED eksternal dipasang pada pin GPIO27:

- LED anoda (+) -> resistor 220Ω -> GPIO27
- LED katoda (-) -> GND

### Wiring dasar
```text
Raspberry Pi 4 Model B
+-----------------------------+
|                             |
|  GPIO27 -> 220Ω -> LED +    |
|  GND    -> LED -           |
|                             |
+-----------------------------+
```

## 3) Status LED sesuai kode
- Saat Wi-Fi/GCS terhubung -> LED menyala solid
- Saat koneksi terputus -> LED berkedip cepat

## 4) Kontrol dari web
- Web panel sekarang sudah menyediakan tombol untuk menggerakkan servo 1 dan servo 2.
- Perintah dikirim lewat Socket.IO ke node Pi.
- Node Pi menerima event `pi_servo_command` dari GCS bridge.
