from flask import Flask, render_template_string, request, redirect, url_for, session, flash
import sqlite3
import random
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
# Fallback seguro por si falla la variable de entorno
app.secret_key = os.getenv('SECRET_KEY', 'clave_secreta_para_sesiones_erp_generico')
DATABASE = 'inventario.db'

# Lista de códigos de credenciales de trabajadores autorizados
CREDENCIALES_VALIDAS = [
    "223476", "115982", "334812", "449201", "556172",
    "668394", "772105", "883940", "992813", "123456",
    "654321", "789123", "456789", "987654", "246810" 
]

# ==========================================
# ESTRUCTURA DE BASE DE DATOS Y CATÁLOGO EMBEBIDO
# ==========================================
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            telefono TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            marca TEXT NOT NULL,
            stock_total INTEGER NOT NULL,
            stock_disponible INTEGER NOT NULL,
            precio_alquiler REAL NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipo_id INTEGER,
            cliente TEXT NOT NULL,
            telefono_cliente TEXT NOT NULL,
            fecha_inicio TEXT NOT NULL,
            fecha_fin TEXT NOT NULL,
            cantidad INTEGER NOT NULL DEFAULT 1,
            precio_total REAL NOT NULL,
            activo INTEGER DEFAULT 1,
            FOREIGN KEY (equipo_id) REFERENCES equipos(id)
        )
    ''')
    
    cursor.execute("SELECT * FROM usuarios WHERE username='admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO usuarios (username, password, nombre, email, telefono) VALUES ('admin', 'admin123', 'Administrador General', 'soporte@empresa.com', '999999999')")
    
    # ---------------------------------------------------------
    # MATRIZ DE INVENTARIO HARDCODEADA (A PRUEBA DE NUBE)
    # ---------------------------------------------------------
    cursor.execute("SELECT COUNT(*) FROM equipos")
    if cursor.fetchone()[0] == 0:
        print("[DATA-CORE] Inicializando base de datos con catálogo embebido (Hardcoded Matrix)...")
        
        # Diccionario con el inventario real procesado desde el archivo TADEEM
        # Formato: "Nombre Técnico" : ("MARCA", Stock_Total)
        inventario_embebido = {
            "DELL Latitude 3420 | Core i5-1135G7 | 8GB": ("DELL", 1),
            "DELL Latitude 3420 (A0247) | Core i5-1135G7 | 16GB": ("DELL", 1),
            "DELL Latitude 3420 (A0248) | Core i5-1135G7 | 16GB": ("DELL", 1),
            "DELL Latitude 3520 | Core i7-1165G7 | 24GB": ("DELL", 20),
            "DELL Latitude 3520 | Core i7-1165G7 | 8GB": ("DELL", 59),
            "DELL Latitude 5420 | Core i5-1135G7 | 16GB": ("DELL", 1),
            "DELL Latitude 5520 | Core i7-1185G7 | 16GB": ("DELL", 2),
            "DELL Latutude 3420 | Core i5-1135G7 | 16GB": ("DELL", 1),
            "DELL Precision 3551 (A0315) | Core i7-10850H | 32GB": ("DELL", 1),
            "DELL ThinkPad L15 Gen2 | Core i5-1135G7 | 16GB": ("DELL", 1),
            "DELL Vostro 3400 | Core i5-1135G7 | 16GB": ("DELL", 1),
            
            "HP 250 G10 | Core i7-1355U | 16GB": ("HP", 1),
            "HP 250 G9 | Core i7-1255U | 16GB": ("HP", 44),
            "HP 348 G7 | Core i7-10510U | 16GB": ("HP", 25),
            "HP Victus 15-fa0007la | Core i5-12450H | 16GB": ("HP", 6),
            "HP Victus 16-d1007la | Core i5-12500H | 16GB": ("HP", 1),
            "HP ZBook Power 15.6 Inch G9 | Core i7-12700H | 32GB": ("HP", 1),
            "HP Zbook Firefly 14 G8 | Core i7-1165G7 | 16GB": ("HP", 1),
            
            "LENOVO IdeaPad 5 14IIL05 | Core i5-1035G1 | 8GB": ("LENOVO", 1),
            "LENOVO IdeaPad Gaming 3 15IHU6 | Core i5-11300H | 16GB": ("LENOVO", 2),
            "LENOVO LOQ 15IAX9 | Core i5-12450HX | 16GB": ("LENOVO", 14),
            "LENOVO LOQ 15IRH8 | Core i5-13420H | 16GB": ("LENOVO", 23),
            "LENOVO LOQ 15IRX9 | Core i5-12450HX | 16GB": ("LENOVO", 25),
            "LENOVO ThinkBook 14-IML | Core i5-10210U | 8GB": ("LENOVO", 10),
            "LENOVO ThinkBook 15 G2 ITL | Core i5-1135G7 | 8GB": ("LENOVO", 3),
            "LENOVO ThinkPad E14 Gen 2 | Core i7-1165G7 | 8GB": ("LENOVO", 7),
            "LENOVO ThinkPad E14 Gen2 | Core i5-1135G7 | 16GB": ("LENOVO", 32),
            "LENOVO ThinkPad E15 | Core i7-10510U | 16GB": ("LENOVO", 1),
            "LENOVO ThinkPad E15 (A0244) | Core i7-10510U | 16GB": ("LENOVO", 1),
            "LENOVO ThinkPad E15 (A0256) | Core i7-10510U | 16GB": ("LENOVO", 1),
            "LENOVO ThinkPad E15 Gen2 | Core i5-1135G7 | 16GB": ("LENOVO", 1),
            "LENOVO ThinkPad L14 Gen 2 | Core i5-1135G7 | 16GB": ("LENOVO", 12),
            "LENOVO ThinkPad L14 Gen2 | Core i5-1135G7 | 16GB": ("LENOVO", 1),
            "LENOVO ThinkPad L15 Gen1 | Core i5-10210U | 16GB": ("LENOVO", 12),
            "LENOVO ThinkPad L15 Gen2 | Core i5-1135G7 | 16GB": ("LENOVO", 3),
            "LENOVO ThinkPad L490 | Core i5-8265U | 16GB": ("LENOVO", 1),
            "LENOVO ThinkPad L580 | Core i5-8250U | 8GB": ("LENOVO", 1),
            "LENOVO ThinkPad P14s Gen4 | Core i7-1360P | 16GB": ("LENOVO", 1),
            "LENOVO ThinkPad T14s Gen2 | Core i5-1135G7 | 16GB": ("LENOVO", 1),
            "LENOVO ThinkPad T15 Gen1 | Core i5-10210U | 8GB": ("LENOVO", 1),
            "LENOVO ThinkPad X1 Carbon Gen 9 | Core i7-1165G7 | 16GB": ("LENOVO", 1),
            "LENOVO Thinkbook 15-IML | Core i5-10210U | 8GB": ("LENOVO", 1),
            "LENOVO ThnikPad L15 (A0258) | Core i5-10210U | 16GB": ("LENOVO", 1),
            "LENOVO ThnikPad L15 (A0259) | Core i5-10210U | 16GB": ("LENOVO", 1),
            "LENOVO V14-IIL | Core i5-1035G1 | 8GB": ("LENOVO", 6),
            "LENOVO V15-IIL | Core i5-1035G1 | 8GB": ("LENOVO", 6),
            "LENOVO V15-ILL | Core i5-1035G1 | 8GB": ("LENOVO", 7),
            "Lenovo ThinkBook 15 G2 ITL | Core i5-1135G7 | 8GB": ("LENOVO", 3)
        }
        
        equipos_procesados = []
        for nombre, datos in inventario_embebido.items():
            marca = datos[0].upper().strip()
            stock = datos[1]
            
            # Algoritmo de tasación comercial semanal según rendimiento
            precio_semanal_base = 45.00
            nombre_upper = nombre.upper()
            
            if any(k in nombre_upper for k in ["I9", "XEON", "VICTUS", "LOQ", "ZBOOK"]):
                precio_semanal_base += 55.00  
            elif any(k in nombre_upper for k in ["I7", "RYZEN 7", "PRECISION"]):
                precio_semanal_base += 25.00   
            
            if any(k in nombre_upper for k in ["24GB", "32GB", "64GB"]):
                precio_semanal_base += 15.00   
            elif "8GB" in nombre_upper:
                precio_semanal_base -= 5.00   
                
            equipos_procesados.append((nombre, marca, stock, stock, max(precio_semanal_base, 30.00)))
            
        try:
            cursor.executemany("INSERT INTO equipos (nombre, marca, stock_total, stock_disponible, precio_alquiler) VALUES (?, ?, ?, ?, ?)", equipos_procesados)
            conn.commit()
            print(f"[DATA-CORE] ✅ Auto-importación completada de forma segura. {len(equipos_procesados)} modelos indexados en SQLite.")
        except Exception as e:
            print(f"[DATA-CORE] ❌ Error en el parseo del diccionario nativo: {e}")
            
    conn.close()

# Inicialización forzosa al arranque
init_db()

# ==========================================
# PLANTILLAS DE INTERFAZ GRÁFICA (UI SPA)
# ==========================================

VISTA_LOGIN = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>ERP Control Center - Login</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 flex items-center justify-center h-screen px-4">
    <div class="bg-slate-800 p-6 sm:p-8 rounded-xl shadow-2xl w-full max-w-md border border-slate-700">
        <div class="text-center mb-8">
            <h1 class="text-2xl font-black text-white tracking-tight">SISTEMA ERP</h1>
            <p class="text-slate-400 mt-2 text-xs">Control de Activos & Rentas de Cómputo</p>
        </div>
        {% with messages = get_flashed_messages() %}
          {% if messages %}<div class="bg-indigo-500/20 border border-indigo-500 text-indigo-200 p-3 rounded-lg text-xs mb-4 text-center">{{ messages[0] }}</div>{% endif %}
        {% endwith %}
        <form action="{{ url_for('login') }}" method="POST" class="space-y-5">
            <div>
                <label class="block text-slate-300 text-xs font-semibold mb-2">Usuario Operador</label>
                <input type="text" name="username" required placeholder="Ej: nombre.apellido" class="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500">
            </div>
            <div>
                <label class="block text-slate-300 text-xs font-semibold mb-2">Contraseña</label>
                <input type="password" name="password" required placeholder="••••••••" class="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500">
            </div>
            <button type="submit" class="w-full py-3 bg-indigo-600 text-white font-bold rounded-lg text-sm shadow-lg transition-all hover:bg-indigo-500">Ingresar al Sistema</button>
        </form>
        <div class="mt-6 text-center border-t border-slate-700/60 pt-4">
            <a href="{{ url_for('registro') }}" class="text-xs text-indigo-400 hover:text-indigo-300 font-medium">Registrar nuevo operador corporativo</a>
        </div>
    </div>
</body>
</html>
"""

VISTA_REGISTRO = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>ERP - Registro de Cuenta</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 flex items-center justify-center min-h-screen py-10 px-4">
    <div class="bg-slate-800 p-6 sm:p-8 rounded-xl shadow-2xl w-full max-w-md border border-slate-700">
        <div class="text-center mb-6">
            <h1 class="text-2xl font-bold text-white">Registro de Operador</h1>
            <p class="text-slate-400 mt-1 text-xs">Su credencial de acceso será estructurada automáticamente</p>
        </div>
        {% with messages = get_flashed_messages() %}
          {% if messages %}<div class="bg-rose-500/20 border border-rose-500 text-rose-200 p-3 rounded-lg text-xs mb-4 text-center">{{ messages[0] }}</div>{% endif %}
        {% endwith %}
        <form action="{{ url_for('registro') }}" method="POST" class="space-y-4 text-sm">
            <div>
                <label class="block text-slate-300 text-xs font-semibold uppercase mb-1">Nombre Completo del Colaborador</label>
                <input type="text" name="nombre" required placeholder="Ej: Carlos Mendoza" class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white text-xs focus:outline-none focus:border-indigo-500">
            </div>
            <div>
                <label class="block text-slate-300 text-xs font-semibold uppercase mb-1">Número de Contacto Móvil</label>
                <input type="tel" name="telefono" required placeholder="Ej: 987654321" class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white text-xs focus:outline-none focus:border-indigo-500">
            </div>
            <div>
                <label class="block text-slate-300 text-xs font-semibold uppercase mb-1">Correo Electrónico Corporativo</label>
                <input type="email" name="email" required placeholder="Ej: correo@empresa.com" class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white text-xs focus:outline-none focus:border-indigo-500">
            </div>
            <div>
                <label class="block text-slate-300 text-xs font-semibold uppercase mb-1">Definir Contraseña del Perfil</label>
                <input type="password" name="password" required placeholder="••••••••" class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white text-xs focus:outline-none focus:border-indigo-500">
            </div>
            <button type="submit" class="w-full py-2.5 bg-gradient-to-r from-indigo-600 to-blue-600 text-white font-bold rounded-lg shadow-md hover:opacity-90 transition-all">Continuar al Paso de Validación</button>
        </form>
        <div class="mt-5 text-center border-t border-slate-700/50 pt-3">
            <a href="{{ url_for('index') }}" class="text-xs text-slate-400 underline">Regresar al Panel de Login</a>
        </div>
    </div>
</body>
</html>
"""

VISTA_VERIFICACION = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Seguridad ERP - Validación</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 flex items-center justify-center h-screen px-4">
    <div class="bg-slate-800 p-6 sm:p-8 rounded-xl shadow-2xl w-full max-w-sm border border-slate-700 text-center">
        <h1 class="text-xl font-bold text-white mb-2">Validación de Credenciales</h1>
        <p class="text-slate-400 text-xs mb-6">Por motivos de seguridad, introduce tu Token de Trabajador autorizado para activar la cuenta.</p>
        {% with messages = get_flashed_messages() %}
          {% if messages %}<div class="bg-rose-500/20 border border-rose-500 text-rose-200 p-2.5 rounded-lg text-xs mb-4">{{ messages[0] }}</div>{% endif %}
        {% endwith %}
        <form action="{{ url_for('verificar_codigo') }}" method="POST" class="space-y-4">
            <input type="text" name="codigo_ingresado" required placeholder="Ingresar Token" class="w-full text-center px-4 py-3 bg-slate-900 border border-slate-700 rounded-xl text-lg font-bold text-white focus:outline-none focus:border-indigo-500">
            <button type="submit" class="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-sm rounded-lg shadow-lg transition-all">Validar e Instalar Cuenta</button>
        </form>
        <div class="mt-6 text-center border-t border-slate-700/50 pt-3">
            <a href="{{ url_for('cancelar_registro') }}" class="text-xs text-rose-400 underline">Modificar datos de registro</a>
        </div>
    </div>
</body>
</html>
"""

VISTA_EXITO = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Operación Completada</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 flex items-center justify-center h-screen px-4">
    <div class="bg-slate-800 p-6 sm:p-8 rounded-xl shadow-2xl w-full max-w-md border border-slate-700 text-center space-y-6">
        <div class="inline-flex p-3 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-full">
            <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
        </div>
        <div>
            <h1 class="text-xl font-bold text-white">¡Operador Registrado!</h1>
            <p class="text-slate-400 text-xs mt-1">Tu perfil ha sido inyectado con éxito en la base de datos de la empresa.</p>
        </div>
        <div class="bg-slate-900 p-4 rounded-xl border border-slate-700 text-left space-y-3 text-xs">
            <div>
                <span class="text-xs font-semibold text-slate-400 uppercase">Usuario Asignado:</span>
                <strong class="text-indigo-400 font-mono block text-base select-all">{{ username }}</strong>
            </div>
            <div class="border-t border-slate-800 pt-2">
                <span class="text-xs font-semibold text-slate-400 uppercase">Contraseña:</span>
                <strong class="text-slate-200 font-mono block text-sm">{{ password }}</strong>
            </div>
        </div>
        <a href="{{ url_for('index') }}" class="block w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-sm rounded-lg text-center transition-all">Ir al Inicio de Sesión</a>
    </div>
</body>
</html>
"""

VISTA_DASHBOARD = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>ERP - Control de Activos</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .scrollbar-none::-webkit-scrollbar { display: none; }
        .scrollbar-none { -ms-overflow-style: none; scrollbar-width: none; }
        input[type=number]::-webkit-inner-spin-button, 
        input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
        input[type="date"]::-webkit-calendar-picker-indicator { filter: invert(1); cursor: pointer; }
    </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen font-sans">

    <header class="bg-slate-900 border-b border-slate-800 sticky top-0 z-50 px-4 sm:px-6 py-3">
        <div class="max-w-7xl mx-auto flex flex-col lg:flex-row justify-between items-center gap-4">
            <div class="flex items-center justify-between w-full lg:w-auto">
                <div class="flex items-center space-x-2">
                    <span class="text-lg font-black bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent tracking-wider">ERP MANAGEMENT</span>
                    <span class="bg-slate-950 text-slate-400 text-[10px] px-2 py-0.5 rounded border border-slate-800 font-mono">CORE v5.0</span>
                </div>
                <div class="text-xs text-slate-400 lg:hidden">
                    <a href="{{ url_for('logout') }}" class="bg-rose-500/10 border border-rose-500/20 text-rose-400 px-2.5 py-1 rounded">Salir</a>
                </div>
            </div>
            
            <nav class="flex space-x-1 bg-slate-950 p-1 rounded-lg border border-slate-800 overflow-x-auto whitespace-nowrap max-w-full scrollbar-none w-full lg:w-auto">
                <button onclick="showSection('sec-inventario')" id="btn-sec-inventario" class="tab-btn flex-shrink-0 px-3 sm:px-4 py-2 text-[11px] sm:text-xs font-bold rounded-md transition-all bg-indigo-600 text-white">📦 Control Alquileres</button>
                <button onclick="showSection('sec-analytics')" id="btn-sec-analytics" class="tab-btn flex-shrink-0 px-3 sm:px-4 py-2 text-[11px] sm:text-xs font-bold rounded-md transition-all text-slate-400 hover:text-slate-200">📊 BI & Estadísticas</button>
                <button onclick="showSection('sec-clientes')" id="btn-sec-clientes" class="tab-btn flex-shrink-0 px-3 sm:px-4 py-2 text-[11px] sm:text-xs font-bold rounded-md transition-all text-slate-400 hover:text-slate-200">👥 CRM Historial</button>
                <button onclick="showSection('sec-perfil')" id="btn-sec-perfil" class="tab-btn flex-shrink-0 px-3 sm:px-4 py-2 text-[11px] sm:text-xs font-bold rounded-md transition-all text-slate-400 hover:text-slate-200">👤 Perfil</button>
            </nav>

            <div class="text-xs text-slate-400 hidden lg:block">
                Operador: <span class="text-slate-200 font-semibold mr-3">{{ session['nombre'] }}</span>
                <a href="{{ url_for('logout') }}" class="bg-rose-500/10 border border-rose-500/20 text-rose-400 px-2.5 py-1 rounded hover:bg-rose-600 hover:text-white transition-all">Salir</a>
            </div>
        </div>
    </header>

    <main class="max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
        
        <div id="sec-inventario" class="section-container space-y-6">
            
            <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
                <div class="bg-slate-900 border border-slate-800 p-4 sm:p-5 rounded-2xl flex flex-col justify-between shadow-lg">
                    <span class="text-[10px] sm:text-xs uppercase font-bold tracking-wider text-slate-400">Unidades de Empresa</span>
                    <h3 class="text-2xl sm:text-3xl font-black text-white mt-1 font-mono">{{ stats.unidades_totales }}</h3>
                </div>
                <div class="bg-slate-900 border border-slate-800 p-4 sm:p-5 rounded-2xl flex flex-col justify-between shadow-lg">
                    <span class="text-[10px] sm:text-xs uppercase font-bold tracking-wider text-slate-400">Unidades en Almacén</span>
                    <h3 class="text-2xl sm:text-3xl font-black text-emerald-400 mt-1 font-mono">{{ stats.unidades_disponibles }}</h3>
                </div>
                <div class="bg-slate-900 border border-slate-800 p-4 sm:p-5 rounded-2xl flex flex-col justify-between shadow-lg">
                    <span class="text-[10px] sm:text-xs uppercase font-bold tracking-wider text-slate-400">Laptops Alquiladas</span>
                    <h3 class="text-2xl sm:text-3xl font-black text-indigo-400 mt-1 font-mono">{{ stats.unidades_alquiladas }}</h3>
                </div>
                <div class="bg-slate-900 border border-slate-800 p-4 sm:p-5 rounded-2xl flex flex-col justify-between shadow-lg">
                    <span class="text-[10px] sm:text-xs uppercase font-bold tracking-wider text-slate-400">Modelos de Hardware</span>
                    <h3 class="text-2xl sm:text-3xl font-black text-cyan-400 mt-1 font-mono">{{ stats.total_modelos }}</h3>
                </div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8">
                <div class="lg:col-span-2 space-y-6">
                    <div class="bg-slate-900 p-4 sm:p-6 rounded-xl border border-slate-800 shadow-sm">
                        
                        <div class="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-4 border-b border-slate-800 pb-4">
                            <div>
                                <h2 class="text-base sm:text-lg font-bold text-white mb-2">📦 Catálogo Operativo Real</h2>
                                <div class="flex space-x-2 text-[9px] font-bold">
                                    <span class="bg-sky-500/10 border border-sky-500/20 text-sky-400 px-2 py-1 rounded">DELL</span>
                                    <span class="bg-purple-500/10 border border-purple-500/20 text-purple-400 px-2 py-1 rounded">LENOVO</span>
                                    <span class="bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 px-2 py-1 rounded">HP TECH</span>
                                </div>
                            </div>
                            <div class="w-full sm:w-auto">
                                <p class="text-[10px] text-slate-400 mb-1">💡 Click en una fila para seleccionarla</p>
                                <input type="text" id="inputBuscar" onkeyup="buscarEquipo()" placeholder="Buscar equipo..." class="px-4 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-white focus:outline-none focus:border-indigo-500 w-full sm:w-64">
                            </div>
                        </div>
                        
                        <div class="overflow-x-auto max-h-[480px] rounded-lg border border-slate-800/50">
                            <table class="w-full text-left text-xs text-slate-300" id="tablaEquipos">
                                <thead class="text-slate-400 bg-slate-950 border-b border-slate-800 uppercase tracking-wider sticky top-0 z-10 text-[10px]">
                                    <tr>
                                        <th class="py-3 px-4 min-w-[220px]">Especificaciones Técnicas</th>
                                        <th class="py-3 px-4 text-center">Identidad</th>
                                        <th class="py-3 px-4 text-center">Disponibilidad</th>
                                        <th class="py-3 px-4 text-right">Tarifa Semanal</th>
                                    </tr>
                                </thead>
                                <tbody class="divide-y divide-slate-800/50">
                                    {% for eq in equipos %}
                                    <tr onclick="autoSeleccionarEquipo('{{ eq[0] }}', '{{ eq[5] }}', '{{ eq[4] }}')" class="hover:bg-slate-800/50 transition-colors cursor-pointer group">
                                        <td class="py-3 px-4 font-semibold text-slate-300 group-hover:text-indigo-400 text-[11px] max-w-[260px] md:max-w-none md:whitespace-normal truncate" title="{{ eq[1] }}">{{ eq[1] }}</td>
                                        <td class="py-3 px-4 text-center">
                                            {% if eq[2] == 'DELL' %}
                                                <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/10 border border-sky-500/20 text-sky-400">DELL</span>
                                            {% elif eq[2] == 'LENOVO' %}
                                                <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/10 border border-purple-500/20 text-purple-400">LENOVO</span>
                                            {% else %}
                                                <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">HP</span>
                                            {% endif %}
                                        </td>
                                        <td class="py-3 px-4 text-center font-mono font-bold whitespace-nowrap">
                                            {% if eq[4] > 0 %}
                                                <span class="text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">{{ eq[4] }} / {{ eq[3] }} uds</span>
                                            {% else %}
                                                <span class="text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded">Agotado</span>
                                            {% endif %}
                                        </td>
                                        <td class="py-3 px-4 text-right font-bold text-indigo-400 font-mono whitespace-nowrap">S/. {{ "%.2f"|format(eq[5]) }}</td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <div class="bg-slate-900 p-4 sm:p-6 rounded-xl border border-slate-800 shadow-sm">
                        <h2 class="text-base sm:text-lg font-bold text-white mb-4">🔔 Contratos de Arrendamiento Activos</h2>
                        <div class="overflow-x-auto rounded-lg border border-slate-800/50">
                            <table class="w-full text-left text-xs text-slate-300">
                                <thead class="text-slate-400 bg-slate-950 border-b border-slate-800 uppercase tracking-wider text-[10px]">
                                    <tr>
                                        <th class="py-3 px-4">Cliente / Entidad</th>
                                        <th class="py-3 px-4">Hardware Asignado</th>
                                        <th class="py-3 px-4 text-center">Plazo Vigencia</th>
                                        <th class="py-3 px-4 text-right">Costo Total</th>
                                        <th class="py-3 px-4 text-center">Operación</th>
                                    </tr>
                                </thead>
                                <tbody class="divide-y divide-slate-800/50">
                                    {% for alq in transacciones_activas %}
                                    <tr class="hover:bg-slate-800/20 transition-colors">
                                        <td class="py-3.5 px-4 text-slate-200 font-semibold">{{ alq[2] }}</td>
                                        <td class="py-3.5 px-4 text-white font-mono text-[11px] max-w-[180px] truncate" title="{{ alq[1] }}">
                                            <span class="text-indigo-400 font-black">{{ alq[6] }}x</span> {{ alq[1] }}
                                        </td>
                                        <td class="py-3.5 px-4 text-center text-slate-400 font-mono whitespace-nowrap">{{ alq[3] }} al {{ alq[4] }}</td>
                                        <td class="py-3.5 px-4 text-right font-bold text-indigo-400 font-mono whitespace-nowrap">S/. {{ "%.2f"|format(alq[5]) }}</td>
                                        <td class="py-3.5 px-4 text-center">
                                            <a href="{{ url_for('devolver', transaccion_id=alq[0]) }}" class="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 px-3 py-1 rounded font-bold hover:bg-emerald-500 hover:text-white transition-all text-[11px]">Procesar Retorno</a>
                                        </td>
                                    </tr>
                                    {% else %}
                                    <tr><td colspan="5" class="text-center py-6 text-slate-500">No se registran órdenes de alquiler activas.</td></tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <div class="bg-slate-900 p-5 sm:p-6 rounded-xl border border-slate-800 shadow-sm h-fit">
                    <h2 class="text-base sm:text-lg font-bold text-white mb-1">📝 Registrar Despacho</h2>
                    <p class="text-slate-400 text-[11px] mb-5">Calculo de tarifa dinámico (Mín. 1 semana cobrable).</p>
                    <form action="{{ url_for('procesar_salida') }}" method="POST" class="space-y-4 text-xs">
                        
                        <div class="grid grid-cols-4 gap-3">
                            <div id="contenedor-select" class="col-span-3 transition-all duration-300">
                                <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider">Laptop</label>
                                <select name="equipo_id" id="form-select-equipo" onchange="manejarCambioSelect()" required class="w-full px-2 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white text-[11px] focus:border-indigo-500 truncate">
                                    {% for eq in equipos %}
                                        {% if eq[4] > 0 %}
                                            <option value="{{ eq[0] }}" data-precio="{{ eq[5] }}" data-stock="{{ eq[4] }}">
                                                {{ eq[1] }} (S/. {{ "%.2f"|format(eq[5]) }}/sem)
                                            </option>
                                        {% endif %}
                                    {% endfor %}
                                </select>
                            </div>
                            <div id="contenedor-cantidad" class="col-span-1 transition-all duration-300">
                                <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider text-center">Unds.</label>
                                <input type="number" name="cantidad" id="form-input-cantidad" min="1" value="1" oninput="recalcularPrecio()" required class="w-full px-2 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white font-mono text-center focus:border-indigo-500">
                            </div>
                        </div>

                        <div>
                            <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider">Razón Social del Cliente</label>
                            <input type="text" name="cliente" id="form-input-cliente" required placeholder="Ej: Corporación Industrial S.A." class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white focus:border-indigo-500">
                        </div>
                        <div>
                            <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider">Teléfono de Enlace</label>
                            <input type="tel" name="telefono_cliente" required placeholder="Ej: 999888777" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white">
                        </div>
                        <div class="grid grid-cols-2 gap-3">
                            <div>
                                <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider">Fecha Salida</label>
                                <input type="date" name="fecha_inicio" id="fecha_inicio" onchange="recalcularPrecio()" required class="w-full px-2 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white text-[11px] text-center font-mono">
                            </div>
                            <div>
                                <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider">Fecha Devolución</label>
                                <input type="date" name="fecha_fin" id="fecha_fin" onchange="recalcularPrecio()" required class="w-full px-2 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white text-[11px] text-center font-mono">
                            </div>
                        </div>
                        <div>
                            <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider">Monto Total Dinámico (S/.)</label>
                            <input type="number" step="0.01" name="precio" id="form-input-precio" required placeholder="0.00" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white font-mono font-bold text-sm text-cyan-400">
                        </div>
                        <button type="submit" class="w-full py-3 bg-indigo-600 text-white font-bold rounded-lg shadow-lg text-xs uppercase tracking-wider hover:bg-indigo-500 transition-all">Efectuar Salida de Almacén</button>
                    </form>
                </div>
            </div>
        </div>

        <div id="sec-analytics" class="section-container hidden space-y-6">
            <div class="bg-slate-900 p-4 sm:p-6 rounded-xl border border-slate-800">
                <h2 class="text-base sm:text-lg font-bold text-white mb-1">📊 Inteligencia de Negocios (Business Intelligence)</h2>
                <p class="text-xs text-slate-400 mb-6">Métricas estratégicas calculadas para evaluar la rentabilidad de las líneas de hardware y la concentración del portafolio.</p>
                
                <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6 text-xs">
                    <div class="bg-slate-950 p-4 rounded-xl border border-slate-800/80">
                        <span class="text-[10px] uppercase font-bold text-slate-400 block">Facturación Acumulada</span>
                        <div class="text-lg sm:text-2xl font-black text-cyan-400 mt-1 font-mono">S/. {{ "%.2f"|format(stats.ganancias_totales) }}</div>
                    </div>
                    <div class="bg-slate-950 p-4 rounded-xl border border-slate-800/80">
                        <span class="text-[10px] uppercase font-bold text-slate-400 block">Ticket Medio Contrato</span>
                        <div class="text-lg sm:text-2xl font-black text-indigo-400 mt-1 font-mono">S/. {{ "%.2f"|format(stats.ticket_promedio) }}</div>
                    </div>
                    <div class="bg-slate-950 p-4 rounded-xl border border-slate-800/80">
                        <span class="text-[10px] uppercase font-bold text-slate-400 block">Clientes Únicos</span>
                        <div class="text-lg sm:text-2xl font-black text-white mt-1 font-mono">{{ stats.clientes_unicos }}</div>
                    </div>
                    <div class="bg-slate-950 p-4 rounded-xl border border-slate-800/80">
                        <span class="text-[10px] uppercase font-bold text-slate-400 block">Tasa de Ocupación</span>
                        <div class="text-lg sm:text-2xl font-black text-emerald-400 mt-1 font-mono">{{ "%.1f"|format(stats.tasa_ocupacion) }}%</div>
                    </div>
                </div>

                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div class="bg-slate-950 p-4 rounded-xl border border-slate-800 h-72 sm:h-80 flex flex-col justify-between">
                        <span class="text-xs font-bold text-slate-300 block text-center">Top 5 Clientes Estratégicos (Mayor Volumen de Inversión)</span>
                        <div class="relative h-56 sm:h-64 w-full flex justify-center items-center"><canvas id="chartTopClientes"></canvas></div>
                    </div>
                    <div class="bg-slate-950 p-4 rounded-xl border border-slate-800 h-72 sm:h-80 flex flex-col justify-between">
                        <span class="text-xs font-bold text-slate-300 block text-center">Estructura Logística de Unidades (Disponibles vs Rentadas)</span>
                        <div class="relative h-56 sm:h-64 w-full flex justify-center items-center"><canvas id="chartStock"></canvas></div>
                    </div>
                </div>
            </div>
        </div>

        <div id="sec-clientes" class="section-container hidden space-y-6">
            <div class="bg-slate-900 p-4 sm:p-6 rounded-xl border border-slate-800">
                <h2 class="text-base sm:text-lg font-bold text-white mb-1">👥 Módulo CRM - Base de Datos Transaccional</h2>
                <p class="text-xs text-slate-400 mb-6">Auditoría permanente e histórica de las relaciones comerciales. Fechas procesadas bajo formato Peruano Oficial (DD/MM/AAAA).</p>
                
                <div class="overflow-x-auto rounded-lg border border-slate-800/50">
                    <table class="w-full text-left text-xs text-slate-300">
                        <thead class="text-slate-400 bg-slate-950 border-b border-slate-800 uppercase tracking-wider text-[10px]">
                            <tr>
                                <th class="py-3 px-4">Razón Social / Cliente</th>
                                <th class="py-3 px-4">Contacto Celular</th>
                                <th class="py-3 px-4">Hardware Arrendado</th>
                                <th class="py-3 px-4 text-center">Duración del Contrato</th>
                                <th class="py-3 px-4 text-right">Inversión Total</th>
                                <th class="py-3 px-4 text-center">Estado Logístico</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-800/40">
                            {% for hist in historial_completo %}
                            <tr class="hover:bg-slate-800/20 transition-colors">
                                <td class="py-3 px-4 text-white font-semibold">{{ hist[2] }}</td>
                                <td class="py-3 px-4 text-slate-400 font-mono">{{ hist[3] }}</td>
                                <td class="py-3 px-4 text-slate-300 font-mono text-[11px] max-w-[200px] truncate" title="{{ hist[1] }}">
                                    <span class="text-indigo-400 font-black">{{ hist[9] }}x</span> {{ hist[1] }}
                                </td>
                                <td class="py-3 px-4 text-center text-slate-400 font-mono whitespace-nowrap">{{ hist[4] }} al {{ hist[5] }}</td>
                                <td class="py-3 px-4 text-right font-bold text-cyan-400 font-mono whitespace-nowrap">S/. {{ "%.2f"|format(hist[6]) }}</td>
                                <td class="py-3 px-4 text-center whitespace-nowrap">
                                    {% if hist[8] == 1 %}
                                        <span class="text-amber-400 font-bold bg-amber-500/10 px-2.5 py-0.5 border border-amber-500/20 rounded text-[10px]">Activo en Campo</span>
                                    {% else %}
                                        <span class="text-emerald-400 font-bold bg-emerald-500/10 px-2.5 py-0.5 border border-emerald-500/20 rounded text-[10px]">Cerrado / Devuelto</span>
                                    {% endif %}
                                </td>
                            </tr>
                            {% else %}
                            <tr><td colspan="6" class="text-center py-6 text-slate-500">No se detectan registros comerciales en el CRM local.</td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div id="sec-perfil" class="section-container hidden space-y-6">
            <div class="bg-slate-900 p-6 sm:p-8 rounded-xl border border-slate-800 max-w-2xl mx-auto">
                <div class="flex items-center space-x-4 mb-6">
                    <div class="p-4 bg-indigo-600/10 border border-indigo-500/20 text-indigo-400 rounded-full text-xl font-bold">👤</div>
                    <div>
                        <h2 class="text-lg sm:text-xl font-bold text-white">{{ perfil.nombre }}</h2>
                        <p class="text-xs text-indigo-400">Rango del Sistema: Operador de Inventarios Autorizado</p>
                    </div>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs bg-slate-950 p-6 rounded-xl border border-slate-800">
                    <div>
                        <span class="text-slate-400 block font-semibold mb-0.5">Identificador Único (Login)</span>
                        <span class="text-white font-mono text-sm">{{ session['username'] }}</span>
                    </div>
                    <div>
                        <span class="text-slate-400 block font-semibold mb-0.5">Número de Contacto</span>
                        <span class="text-white font-mono text-sm">{{ perfil.telefono }}</span>
                    </div>
                    <div class="sm:col-span-2 border-t border-slate-800 pt-3 mt-1">
                        <span class="text-slate-400 block font-semibold mb-0.5">Correo Electrónico Registrado</span>
                        <span class="text-white font-mono text-sm text-indigo-300">{{ perfil.email }}</span>
                    </div>
                </div>
            </div>
        </div>

    </main>

    <script>
    let tarifaSugeridaGlobal = 0.0;

    function showSection(sectionId) {
        document.querySelectorAll('.section-container').forEach(sec => sec.classList.add('hidden'));
        document.getElementById(sectionId).classList.remove('hidden');
        
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('bg-indigo-600', 'text-white');
            btn.classList.add('text-slate-400', 'hover:text-slate-200');
        });
        document.getElementById('btn-' + sectionId).classList.remove('text-slate-400', 'hover:text-slate-200');
        document.getElementById('btn-' + sectionId).classList.add('bg-indigo-600', 'text-white');
    }

    function autoSeleccionarEquipo(id, precioSemanal, stockMaximo) {
        const selectEquipo = document.getElementById("form-select-equipo");
        const inputCantidad = document.getElementById("form-input-cantidad");
        const inputCliente = document.getElementById("form-input-cliente");
        
        const divSelect = document.getElementById("contenedor-select");
        const divCantidad = document.getElementById("contenedor-cantidad");
        
        selectEquipo.value = id;
        tarifaSugeridaGlobal = parseFloat(precioSemanal);
        
        if(parseInt(stockMaximo) <= 1) {
            inputCantidad.value = 1;
            divCantidad.style.display = 'none';
            divSelect.classList.remove("col-span-3");
            divSelect.classList.add("col-span-4");
        } else {
            inputCantidad.max = parseInt(stockMaximo);
            inputCantidad.value = 1; 
            divCantidad.style.display = 'block';
            divSelect.classList.remove("col-span-4");
            divSelect.classList.add("col-span-3");
        }
        
        recalcularPrecio();
        
        inputCliente.focus();
        inputCliente.classList.add("border-indigo-500", "ring-2", "ring-indigo-500/20");
        setTimeout(() => {
            inputCliente.classList.remove("border-indigo-500", "ring-2", "ring-indigo-500/20");
        }, 1200);
    }

    function manejarCambioSelect() {
        const select = document.getElementById("form-select-equipo");
        if(select.selectedIndex >= 0) {
            const option = select.options[select.selectedIndex];
            tarifaSugeridaGlobal = parseFloat(option.getAttribute('data-precio') || 0);
            const stockMaximo = parseInt(option.getAttribute('data-stock') || 1);
            
            const divSelect = document.getElementById("contenedor-select");
            const divCantidad = document.getElementById("contenedor-cantidad");
            const inputCantidad = document.getElementById("form-input-cantidad");
            
            if(stockMaximo <= 1) {
                inputCantidad.value = 1;
                divCantidad.style.display = 'none';
                divSelect.classList.remove("col-span-3");
                divSelect.classList.add("col-span-4");
            } else {
                inputCantidad.max = stockMaximo;
                if(parseInt(inputCantidad.value) > stockMaximo) inputCantidad.value = stockMaximo;
                divCantidad.style.display = 'block';
                divSelect.classList.remove("col-span-4");
                divSelect.classList.add("col-span-3");
            }
            recalcularPrecio();
        }
    }

    function recalcularPrecio() {
        const cant = parseInt(document.getElementById("form-input-cantidad").value) || 1;
        const inputPrecio = document.getElementById("form-input-precio");
        
        const fechaInicio = document.getElementById("fecha_inicio").value;
        const fechaFin = document.getElementById("fecha_fin").value;
        
        let semanasRequeridas = 1; 
        
        if(fechaInicio && fechaFin) {
            const d1 = new Date(fechaInicio);
            const d2 = new Date(fechaFin);
            
            const diferenciaMilisegundos = d2 - d1;
            const diferenciaDias = Math.ceil(diferenciaMilisegundos / (1000 * 60 * 60 * 24));
            
            if(diferenciaDias > 0) {
                semanasRequeridas = Math.ceil(diferenciaDias / 7);
            } else if (diferenciaDias < 0) {
                semanasRequeridas = 1; 
            }
        }
        
        inputPrecio.value = (tarifaSugeridaGlobal * cant * semanasRequeridas).toFixed(2);
    }

    function buscarEquipo() {
        var input = document.getElementById("inputBuscar");
        var filter = input.value.toUpperCase();
        var table = document.getElementById("tablaEquipos");
        var tr = table.getElementsByTagName("tr");
        for (var i = 1; i < tr.length; i++) {
            var tdNombre = tr[i].getElementsByTagName("td")[0];
            if (tdNombre) {
                var txtNombre = tdNombre.textContent || tdNombre.innerText;
                if (txtNombre.toUpperCase().indexOf(filter) > -1) {
                    tr[i].style.display = "";
                } else {
                    tr[i].style.display = "none";
                }
            }
        }
    }

    document.addEventListener("DOMContentLoaded", function() {
        manejarCambioSelect();
    });

    const topClientesLabels = {{ stats.top_clientes_labels|tojson }};
    const topClientesData = {{ stats.top_clientes_data|tojson }};

    const ctxClientes = document.getElementById('chartTopClientes').getContext('2d');
    new Chart(ctxClientes, {
        type: 'bar',
        data: {
            labels: topClientesLabels,
            datasets: [{
                data: topClientesData,
                backgroundColor: 'rgba(56, 189, 248, 0.6)',
                borderColor: '#38bdf8',
                borderWidth: 1,
                borderRadius: 5
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, grid: { color: '#1e293b' }, ticks: { color: '#94a3b8', font: { size: 9 } } },
                x: { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 9 } } }
            }
        }
    });

    const ctxStock = document.getElementById('chartStock').getContext('2d');
    new Chart(ctxStock, {
        type: 'doughnut',
        data: {
            labels: ['Uds en Almacén (Disponibles)', 'Uds en Campo (Rentadas)'],
            datasets: [{
                data: [{{ graph_data.stock_disp }}, {{ graph_data.stock_alqu }}],
                backgroundColor: ['rgba(52, 211, 153, 0.6)', 'rgba(99, 102, 241, 0.6)'],
                borderColor: ['#34d399', '#6366f1'],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 } } } }
        }
    });
    </script>
</body>
</html>
"""

# ==========================================
# PROCESADORES BACKEND (RUTAS CONTROL CENTRAL)
# ==========================================

@app.route('/')
def index():
    if 'usuario_id' in session:
        return redirect(url_for('dashboard'))
    return render_template_string(VISTA_LOGIN)

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, nombre FROM usuarios WHERE username=? AND password=?", (username, password))
    user = cursor.fetchone()
    conn.close()
    if user:
        session['usuario_id'] = user[0]
        session['username'] = user[1]
        session['nombre'] = user[2]
        return redirect(url_for('dashboard'))
    else:
        flash("Las credenciales ingresadas son inválidas.")
        return redirect(url_for('index'))

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']
        telefono = request.form['telefono']
        email = request.form['email']
        password = request.form['password']
        
        partes_nombre = nombre.lower().strip().split()
        username_generado = f"{partes_nombre[0]}.{partes_nombre[1]}" if len(partes_nombre) >= 2 else partes_nombre[0]
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM usuarios WHERE username=? OR email=?", (username_generado, email))
        if cursor.fetchone():
            conn.close()
            flash("El usuario o correo electrónico ya existen.")
            return render_template_string(VISTA_REGISTRO)
        conn.close()
        
        session['temp_registro'] = {
            'nombre': nombre, 'username': username_generado,
            'telefono': telefono, 'email': email,
            'password': password
        }
        return redirect(url_for('verificar_codigo'))
    return render_template_string(VISTA_REGISTRO)

@app.route('/verificar-codigo', methods=['GET', 'POST'])
def verificar_codigo():
    if 'temp_registro' not in session:
        return redirect(url_for('registro'))
    if request.method == 'POST':
        codigo_ingresado = request.form['codigo_ingresado'].strip()
        datos_temp = session['temp_registro']
        
        if codigo_ingresado in CREDENCIALES_VALIDAS:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            try:
                cursor.execute('INSERT INTO usuarios (username, password, nombre, email, telefono) VALUES (?, ?, ?, ?, ?)',
                               (datos_temp['username'], datos_temp['password'], datos_temp['nombre'], datos_temp['email'], datos_temp['telefono']))
                conn.commit()
                conn.close()
                u, p = datos_temp['username'], datos_temp['password']
                session.pop('temp_registro', None)
                return render_template_string(VISTA_EXITO, username=u, password=p)
            except sqlite3.IntegrityError:
                conn.close()
                flash("Error de duplicidad. Verifique sus datos.")
        else:
            flash("Token de trabajador inválido o no autorizado.")
    return render_template_string(VISTA_VERIFICACION)

@app.route('/cancelar-registro')
def cancelar_registro():
    session.pop('temp_registro', None)
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session:
        return redirect(url_for('index'))
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, nombre, marca, stock_total, stock_disponible, precio_alquiler FROM equipos")
    equipos = cursor.fetchall()
    
    cursor.execute("SELECT t.id, e.nombre, t.cliente, t.fecha_inicio, t.fecha_fin, t.precio_total, t.cantidad FROM transacciones t JOIN equipos e ON t.equipo_id = e.id WHERE t.activo = 1")
    transacciones_activas = cursor.fetchall()
    
    cursor.execute("SELECT t.id, e.nombre, t.cliente, t.telefono_cliente, t.fecha_inicio, t.fecha_fin, t.precio_total, 'Alquiler', t.activo, t.cantidad FROM transacciones t JOIN equipos e ON t.equipo_id = e.id ORDER BY t.id DESC")
    historial_completo = cursor.fetchall()
    
    cursor.execute("SELECT nombre, email, telefono FROM usuarios WHERE id=?", (session['usuario_id'],))
    perfil = cursor.fetchone()
    perfil_dict = {'nombre': perfil[0], 'email': perfil[1], 'telefono': perfil[2]} if perfil else {'nombre': session['nombre'], 'email': '-', 'telefono': '-'}

    cursor.execute("SELECT COUNT(*), SUM(stock_disponible), SUM(stock_total) FROM equipos")
    res_eq = cursor.fetchone()
    total_modelos = res_eq[0] or 0
    stock_disp = res_eq[1] or 0
    stock_total_corp = res_eq[2] or 0
    stock_alqu = stock_total_corp - stock_disp
    
    tasa_ocupacion = (stock_alqu / stock_total_corp * 100) if stock_total_corp > 0 else 0.0

    cursor.execute("SELECT COUNT(*), SUM(precio_total), AVG(precio_total), COUNT(DISTINCT cliente) FROM transacciones")
    res_trans = cursor.fetchone()
    total_transacciones = res_trans[0] or 0
    ganancias_totales = res_trans[1] or 0.0
    ticket_promedio = res_trans[2] or 0.0
    clientes_unicos = res_trans[3] or 0

    cursor.execute("SELECT cliente, SUM(precio_total) FROM transacciones GROUP BY cliente ORDER BY SUM(precio_total) DESC LIMIT 5")
    res_top = cursor.fetchall()
    top_clientes_labels = [r[0] for r in res_top] or ["Sin Transacciones"]
    top_clientes_data = [r[1] for r in res_top] or [0]

    stats = {
        'total_modelos': total_modelos, 'unidades_disponibles': stock_disp, 'unidades_totales': stock_total_corp,
        'unidades_alquiladas': stock_alqu,
        'tasa_ocupacion': tasa_ocupacion, 'total_transacciones': total_transacciones,
        'ganancias_totales': ganancias_totales, 'ticket_promedio': ticket_promedio,
        'clientes_unicos': clientes_unicos,
        'top_clientes_labels': top_clientes_labels, 'top_clientes_data': top_clientes_data
    }
    graph_data = {'stock_disp': stock_disp, 'stock_alqu': stock_alqu}
    
    conn.close()
    return render_template_string(VISTA_DASHBOARD, equipos=equipos, transacciones_activas=transacciones_activas, historial_completo=historial_completo, perfil=perfil_dict, stats=stats, graph_data=graph_data)

@app.route('/procesar-salida', methods=['POST'])
def procesar_salida():
    if 'usuario_id' not in session: return redirect(url_for('index'))
    equipo_id = int(request.form['equipo_id'])
    cantidad = int(request.form.get('cantidad', 1))
    cliente = request.form['cliente']
    telefono_cliente = request.form['telefono_cliente']
    fecha_inicio_raw = request.form['fecha_inicio']
    fecha_fin_raw = request.form['fecha_fin']
    precio = float(request.form['precio'])
    
    try:
        fecha_inicio = datetime.strptime(fecha_inicio_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
        fecha_fin = datetime.strptime(fecha_fin_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        fecha_inicio = fecha_inicio_raw
        fecha_fin = fecha_fin_raw
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT stock_disponible FROM equipos WHERE id=?", (equipo_id,))
    stock_actual = cursor.fetchone()
    
    if stock_actual and stock_actual[0] >= cantidad:
        cursor.execute("UPDATE equipos SET stock_disponible = stock_disponible - ? WHERE id=?", (cantidad, equipo_id))
        cursor.execute('''
            INSERT INTO transacciones (equipo_id, cliente, telefono_cliente, fecha_inicio, fecha_fin, cantidad, precio_total, activo) 
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        ''', (equipo_id, cliente, telefono_cliente, fecha_inicio, fecha_fin, cantidad, precio))
        conn.commit()
        flash(f"Salida registrada: {cantidad} unidades arrendadas al cliente {cliente}.")
    else:
        flash(f"Error: Stock insuficiente. Solo quedan {stock_actual[0] if stock_actual else 0} unidades.")
        
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/devolver/<int:transaccion_id>')
def devolver(transaccion_id):
    if 'usuario_id' not in session: return redirect(url_for('index'))
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT equipo_id, cantidad FROM transacciones WHERE id=?", (transaccion_id,))
    res = cursor.fetchone()
    if res:
        eq_id, cant = res
        cursor.execute("UPDATE transacciones SET activo = 0 WHERE id=?", (transaccion_id,))
        cursor.execute("UPDATE equipos SET stock_disponible = stock_disponible + ? WHERE id=?", (cant, eq_id))
        conn.commit()
        flash(f"Retorno confirmado. {cant} unidades reintegradas al inventario físico.")
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)