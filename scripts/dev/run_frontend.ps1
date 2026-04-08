Set-Location "D:\CRYPTOTEHNOLOG\dashboard-frontend"
# Local Vite startup workaround for Windows/sandbox spawn EPERM during config loading.
# This is dev-only and does not change product runtime behavior.
& npm run dev -- --configLoader runner --host 127.0.0.1 --port 5173
