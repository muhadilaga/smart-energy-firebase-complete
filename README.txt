SMART ENERGY FIREBASE DASHBOARD

1. Extract ZIP.
2. Buka folder smart-energy-firebase-complete.
3. Folder "public" ada di dalamnya.
4. Untuk menjalankan dashboard lokal:
   - buka Command Prompt di folder ini
   - jalankan: python -m http.server 8000 -d public
5. Buka http://localhost:8000
6. Login dengan akun Firebase Authentication yang sudah dibuat.

Catatan:
- Database Rules saat ini hanya mengizinkan read jika auth != null.
- ESP32 belum diberi akses write.
