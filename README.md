# TongKas

Aplikasi pencatat keuangan sederhana untuk UMKM, dibangun sebagai aplikasi multi-tier
(Flask + PostgreSQL + Redis) yang seluruhnya berjalan di Docker Compose.

Projek UTS Cloud Services, Semester 5.

## Latar Belakang dan Alasan Projek

[Tulis dengan kata-kata Anda: masalah UMKM yang tidak mencatat keuangan, mengapa memilih
projek ini, dan kaitannya dengan peran karier yang Anda tuju.]

## Fitur

- Catat pemasukan dan pengeluaran dengan kategori
- Ringkasan masuk, keluar, dan laba otomatis
- Filter per bulan, hapus transaksi, dan export CSV
- Cache Redis untuk `GET /transactions` (header `X-Cache: HIT/MISS`)

## Arsitektur

```mermaid
flowchart TD
    B[Browser] -->|localhost:8080| APP
    subgraph NET[network: tongkas_backend]
        APP[app<br/>Flask + gunicorn :8000]
        REDIS[(redis :6379)]
        DB[(db PostgreSQL :5432)]
        ADM[adminer :8080<br/>profile tools]
        APP -->|1. cek cache| REDIS
        APP -->|2. jika MISS| DB
        ADM --> DB
    end
    DB --- V1[(volume pgdata)]
    REDIS --- V2[(volume redisdata)]
    B2[Browser] -->|localhost:8081| ADM
```

| Container | Image | Port host | Volume | Healthcheck |
|---|---|---|---|---|
| app | build lokal (multi-stage) | 8080 | - | - |
| db | postgres:16.4-alpine | tidak dibuka | pgdata | pg_isready |
| redis | redis:7.4-alpine | tidak dibuka | redisdata | redis-cli ping |
| adminer (profile tools) | adminer:4.8.1 | 8081 | - | - |

## Cara Menjalankan

Prasyarat: Docker Desktop.

```bash
git clone https://github.com/<username>/tongkas.git
cd tongkas
cp .env.example .env      # Windows CMD/PowerShell: copy .env.example .env
docker compose up -d --build
```

Buka http://localhost:8080

Opsional, Adminer (profile `tools`):

```bash
docker compose --profile tools up -d
```

Buka http://localhost:8081 (System: PostgreSQL, Server: `db`, user dan password sesuai `.env`).

Menghentikan: `docker compose down` (data tetap ada) atau `docker compose down -v` (data dihapus).

## Endpoint

| Method | Path | Keterangan | Status |
|---|---|---|---|
| GET | /health | cek aplikasi, database, dan cache | 200 / 503 |
| GET | /transactions | daftar dan ringkasan (`?month=YYYY-MM`) | 200 / 400 |
| POST | /transactions | tambah transaksi | 201 / 400 |
| DELETE | /transactions/{id} | hapus transaksi | 204 / 404 |
| GET | /export.csv | unduh CSV | 200 |

## Screenshot

## Screenshot

### Bagian b: Dockerfile
Ukuran image:
![docker images](screenshots/screenshot_bagian-b.jpeg)

Ukuran image dan layer (`docker history`) yang membuktikan multi-stage build:
![docker history](screenshots/screenshot_bagian-b-2.jpeg)

### Bagian c: Docker Compose
Service berjalan, db dan redis `healthy`:
![docker compose ps](screenshots/screenshot_bagian-c.jpeg)

Profile `tools` (Adminer):
![profile tools](screenshots/screenshot_bagian-c-2.jpeg)

`.env` diabaikan Git:
![gitignore](screenshots/screenshot_bagian-c-3.jpeg)

### Bagian d: Bukti berjalan di localhost
d(2) Uji endpoint, health `200` dan POST `201`:
![health dan POST](screenshots/screenshot_bagian-d.jpeg)

d(2) Cache `MISS` lalu `HIT`, dan validasi `400`:
![cache dan validasi](screenshots/screenshot_bagian-d-3.jpeg)

d(3) Persistensi, data sebelum `down`:
![sebelum down](screenshots/screenshot_bagian-d-4.jpeg)

d(3) `docker compose down` lalu `up -d` (volume tetap ada):
![down dan up](screenshots/screenshot_bagian-d-5.jpeg)

d(3) Data masih ada setelah `up`:
![sesudah up](screenshots/screenshot_bagian-d-6.jpeg)

d(3) `docker compose down -v` (volume dihapus, data hilang):
![down -v](screenshots/screenshot_bagian-d-7.jpeg)

Catatan: pesan `Network tongkas_backend Resource is still in use` muncul karena container
Adminer (profile `tools`) masih terhubung ke network yang sama. Itu bukan error aplikasi.

### Tampilan aplikasi
![aplikasi](screenshots/tampilanUI.jpeg)
![adminer](screenshots/adminer.jpeg)

## Tautan

- Video demo: [isi setelah diunggah]
- Artikel: [isi setelah terbit]

## AI Usage Declaration

Saya menggunakan Claude (Anthropic) sebagai asisten untuk [sesuaikan: menyusun kerangka kode,
meninjau Dockerfile dan docker-compose, menyusun draf dokumentasi]. Saya menjalankan, menguji,
dan memahami seluruh kode, serta menulis narasi video dan artikel dengan kata-kata sendiri.