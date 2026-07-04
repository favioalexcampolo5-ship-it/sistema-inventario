from flask import Flask, render_template_string, request, redirect, url_for, session, flash, Response
import psycopg2
from psycopg2 import IntegrityError
import os
import io
import csv
from datetime import datetime
from dotenv import load_dotenv
from fpdf import FPDF

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'clave_secreta_para_sesiones_erp_generico')

# ==========================================
# BLINDAJE ANTI-CACHÉ
# ==========================================
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# Lista de códigos de credenciales de trabajadores autorizados
CREDENCIALES_VALIDAS = [
    "223476", "115982", "334812", "449201", "556172",
    "668394", "772105", "883940", "992813", "123456",
    "654321", "789123", "456789", "987654", "246810" 
]

DB_URL = os.getenv('DATABASE_URL')
if DB_URL and DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

def get_db_connection():
    return psycopg2.connect(DB_URL)

# ==========================================
# ESTRUCTURA DE BASE DE DATOS Y CATÁLOGO
# ==========================================
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            telefono TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipos (
            id SERIAL PRIMARY KEY,
            nombre TEXT NOT NULL,
            marca TEXT NOT NULL,
            stock_total INTEGER NOT NULL,
            stock_disponible INTEGER NOT NULL,
            precio_alquiler NUMERIC NOT NULL
        )
    ''')
    
    # ¡CLAVE! Ejecutar los ALTER TABLE fuera del condicional para forzar la migración
    try:
        cursor.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS precio_mercado NUMERIC DEFAULT 2500")
        cursor.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS stock_mantenimiento INTEGER DEFAULT 0")
        conn.commit()
    except Exception as e:
        print(f"[DATA-CORE] Error en la migración de columnas: {e}")
        conn.rollback()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transacciones (
            id SERIAL PRIMARY KEY,
            equipo_id INTEGER,
            cliente TEXT NOT NULL,
            telefono_cliente TEXT NOT NULL,
            fecha_inicio TEXT NOT NULL,
            fecha_fin TEXT NOT NULL,
            cantidad INTEGER NOT NULL DEFAULT 1,
            precio_total NUMERIC NOT NULL,
            activo INTEGER DEFAULT 1,
            FOREIGN KEY (equipo_id) REFERENCES equipos(id)
        )
    ''')
    
    cursor.execute("SELECT * FROM usuarios WHERE username='admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO usuarios (username, password, nombre, email, telefono) VALUES ('admin', 'admin123', 'Administrador General', 'soporte@empresa.com', '999999999')")
    
    cursor.execute("SELECT COUNT(*) FROM equipos")
    if cursor.fetchone()[0] == 0:
        inventario_embebido = {
            "DELL Latitude 3420 | Core i5-1135G7 | 8GB": ("DELL", 1),
            "DELL Latitude 3520 | Core i7-1165G7 | 24GB": ("DELL", 20),
            "DELL Latitude 3520 | Core i7-1165G7 | 8GB": ("DELL", 59),
            "HP 250 G9 | Core i7-1255U | 16GB": ("HP", 44),
            "HP 348 G7 | Core i7-10510U | 16GB": ("HP", 25),
            "HP Victus 15-fa0007la | Core i5-12450H | 16GB": ("HP", 6),
            "LENOVO LOQ 15IAX9 | Core i5-12450HX | 16GB": ("LENOVO", 14),
            "LENOVO LOQ 15IRH8 | Core i5-13420H | 16GB": ("LENOVO", 23),
            "LENOVO LOQ 15IRX9 | Core i5-12450HX | 16GB": ("LENOVO", 25),
            "LENOVO ThinkBook 14-IML | Core i5-10210U | 8GB": ("LENOVO", 10),
            "LENOVO ThinkPad E14 Gen2 | Core i5-1135G7 | 16GB": ("LENOVO", 32),
            "LENOVO ThinkPad L14 Gen 2 | Core i5-1135G7 | 16GB": ("LENOVO", 12),
            "LENOVO V15-ILL | Core i5-1035G1 | 8GB": ("LENOVO", 7)
        }
        
        equipos_procesados = []
        for nombre, datos in inventario_embebido.items():
            marca = datos[0].upper().strip()
            stock = datos[1]
            precio_semanal_base = 45.00
            precio_mercado_estimado = 2200.00
            nombre_upper = nombre.upper()
            
            if any(k in nombre_upper for k in ["I9", "XEON", "VICTUS", "LOQ", "ZBOOK"]):
                precio_semanal_base += 55.00  
                precio_mercado_estimado += 2500.00
            elif any(k in nombre_upper for k in ["I7", "RYZEN 7", "PRECISION"]):
                precio_semanal_base += 25.00   
                precio_mercado_estimado += 1300.00
            if any(k in nombre_upper for k in ["24GB", "32GB", "64GB"]):
                precio_semanal_base += 15.00   
                precio_mercado_estimado += 700.00
            elif "8GB" in nombre_upper:
                precio_semanal_base -= 5.00   
                precio_mercado_estimado -= 300.00
                
            equipos_procesados.append((nombre, marca, stock, stock, max(precio_semanal_base, 30.00), precio_mercado_estimado))
            
        try:
            cursor.execute("TRUNCATE TABLE equipos CASCADE") 
            cursor.executemany("INSERT INTO equipos (nombre, marca, stock_total, stock_disponible, precio_alquiler, precio_mercado) VALUES (%s, %s, %s, %s, %s, %s)", equipos_procesados)
            conn.commit()
        except Exception as e:
            print(f"[DATA-CORE] ❌ Error inyectando datos: {e}")
            
    conn.close()

# ==========================================
# PLANTILLAS HTML
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
                    <span class="bg-slate-950 text-slate-400 text-[10px] px-2 py-0.5 rounded border border-slate-800 font-mono">CLOUD DB v10.0</span>
                </div>
                <div class="text-xs text-slate-400 lg:hidden flex space-x-2">
                    <a href="{{ url_for('dashboard') }}" class="bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 px-2.5 py-1 rounded">🔄 Sync</a>
                    <a href="{{ url_for('logout') }}" class="bg-rose-500/10 border border-rose-500/20 text-rose-400 px-2.5 py-1 rounded">Salir</a>
                </div>
            </div>
            
            <nav class="flex space-x-1 bg-slate-950 p-1 rounded-lg border border-slate-800 overflow-x-auto whitespace-nowrap max-w-full scrollbar-none w-full lg:w-auto">
                <button onclick="showSection('sec-inventario')" id="btn-sec-inventario" class="tab-btn flex-shrink-0 px-3 sm:px-4 py-2 text-[11px] sm:text-xs font-bold rounded-md transition-all bg-indigo-600 text-white">📦 Control Alquileres</button>
                <button onclick="showSection('sec-mantenimiento')" id="btn-sec-mantenimiento" class="tab-btn flex-shrink-0 px-3 sm:px-4 py-2 text-[11px] sm:text-xs font-bold rounded-md transition-all text-slate-400 hover:text-slate-200">🛠️ Taller Técnico</button>
                <button onclick="showSection('sec-analytics')" id="btn-sec-analytics" class="tab-btn flex-shrink-0 px-3 sm:px-4 py-2 text-[11px] sm:text-xs font-bold rounded-md transition-all text-slate-400 hover:text-slate-200">📊 BI & Estadísticas</button>
                <button onclick="showSection('sec-clientes')" id="btn-sec-clientes" class="tab-btn flex-shrink-0 px-3 sm:px-4 py-2 text-[11px] sm:text-xs font-bold rounded-md transition-all text-slate-400 hover:text-slate-200">👥 CRM Historial</button>
            </nav>

            <div class="text-xs text-slate-400 hidden lg:flex items-center space-x-4">
                <span>Operador: <strong class="text-slate-200">{{ session['nombre'] }}</strong></span>
                <a href="{{ url_for('dashboard') }}" class="bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 px-3 py-1.5 rounded hover:bg-indigo-600 hover:text-white transition-all font-bold">🔄 Sincronizar Datos</a>
                <a href="{{ url_for('logout') }}" class="bg-rose-500/10 border border-rose-500/20 text-rose-400 px-3 py-1.5 rounded hover:bg-rose-600 hover:text-white transition-all font-bold">Salir</a>
            </div>
        </div>
    </header>

    <main class="max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
        
        {% if alertas_devolucion %}
        <div class="space-y-2">
            {% for alerta in alertas_devolucion %}
            <div class="bg-amber-500/10 border border-amber-500/30 rounded-xl p-3 flex flex-col sm:flex-row justify-between items-start sm:items-center text-xs text-amber-200 gap-2 shadow-md">
                <div class="flex items-center space-x-2">
                    <span class="text-base">⚠️</span>
                    <span><strong>ALERTA LOGÍSTICA:</strong> El contrato de <strong>{{ alerta.cliente }}</strong> ({{ alerta.equipo }}) {{ alerta.mensaje }}.</span>
                </div>
                <span class="bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded font-mono font-bold text-[10px] uppercase">Contacto: {{ alerta.telefono }}</span>
            </div>
            {% endfor %}
        </div>
        {% endif %}
        
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="bg-indigo-500/20 border border-indigo-500 text-indigo-200 p-4 rounded-xl text-sm font-semibold shadow-lg text-center">{{ messages[0] }}</div>
            {% endif %}
        {% endwith %}

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
                                <p class="text-[10px] text-slate-400">Selecciona cualquier equipo para abrir el menú de gestión avanzada.</p>
                            </div>
                            <div class="w-full sm:w-auto flex flex-col sm:flex-row gap-2">
                                <button onclick="document.getElementById('modal-add').classList.remove('hidden')" class="bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-bold py-2 px-4 rounded-lg shadow-lg transition-all whitespace-nowrap">➕ Añadir Hardware</button>
                                <a href="{{ url_for('exportar_inventario') }}" class="bg-amber-500 hover:bg-amber-400 text-white text-[11px] font-bold py-2 px-4 rounded-lg shadow-lg transition-all whitespace-nowrap text-center">📥 Exportar Excel</a>
                                <input type="text" id="inputBuscar" onkeyup="buscarEquipo()" placeholder="Buscar equipo..." class="px-4 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-white focus:outline-none focus:border-indigo-500 w-full">
                            </div>
                        </div>
                        <div class="overflow-x-auto max-h-[480px] rounded-lg border border-slate-800/50">
                            <table class="w-full text-left text-xs text-slate-300" id="tablaEquipos">
                                <thead class="text-slate-400 bg-slate-950 border-b border-slate-800 uppercase tracking-wider sticky top-0 z-10 text-[10px]">
                                    <tr>
                                        <th class="py-3 px-4 min-w-[220px]">Especificaciones Técnicas</th>
                                        <th class="py-3 px-4 text-center">Identidad</th>
                                        <th class="py-3 px-4 text-center">Disp.</th>
                                        <th class="py-3 px-4 text-right">Tarifa (Sem)</th>
                                        <th class="py-3 px-4 text-center">Acciones</th>
                                    </tr>
                                </thead>
                                <tbody class="divide-y divide-slate-800/50">
                                    {% for eq in equipos %}
                                    <tr onclick="abrirModuloEquipo('{{ eq[0] }}', '{{ eq[1] }}', '{{ eq[2] }}', '{{ eq[4] }}', '{{ eq[3] }}', '{{ eq[5] }}', '{{ eq[6] }}')" class="hover:bg-slate-800/50 transition-colors cursor-pointer group">
                                        <td class="py-3 px-4 font-semibold text-slate-300 group-hover:text-indigo-400 text-[11px] max-w-[220px] md:max-w-none md:whitespace-normal truncate" title="{{ eq[1] }}">{{ eq[1] }}</td>
                                        <td class="py-3 px-4 text-center">
                                            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-950 border border-slate-800 text-slate-300">{{ eq[2] }}</span>
                                        </td>
                                        <td class="py-3 px-4 text-center font-mono font-bold whitespace-nowrap">
                                            {% if eq[4] > 0 %}
                                                <span class="text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">{{ eq[4] }} / {{ eq[3] }}</span>
                                            {% else %}
                                                <span class="text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded">Agotado</span>
                                            {% endif %}
                                        </td>
                                        <td class="py-3 px-4 text-right font-bold text-indigo-400 font-mono whitespace-nowrap">S/. {{ "%.2f"|format(eq[5]) }}</td>
                                        <td class="py-3 px-4 text-center">
                                            <form action="{{ url_for('eliminar_equipo', equipo_id=eq[0]) }}" method="POST" onsubmit="return confirm('¿Seguro que deseas eliminar este equipo del catálogo?');">
                                                <button type="submit" onclick="event.stopPropagation()" class="text-rose-400 hover:text-white hover:bg-rose-600 font-bold bg-rose-500/10 px-2 py-1.5 rounded text-[10px] transition-all">Eliminar</button>
                                            </form>
                                        </td>
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
                                        <td class="py-3.5 px-4 text-center flex justify-center space-x-2 whitespace-nowrap">
                                            <a href="{{ url_for('descargar_pdf', t_id=alq[0]) }}" target="_blank" class="bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 px-2 py-1 rounded font-bold hover:bg-indigo-600 hover:text-white transition-all text-[11px]" title="Generar PDF">📄 PDF</a>
                                            <button onclick="abrirModalEdicionUnidades('{{ alq[0] }}', '{{ alq[2] }}', '{{ alq[6] }}', '{{ alq[1] }}')" class="bg-sky-500/10 border border-sky-500/20 text-sky-400 px-2 py-1 rounded font-bold hover:bg-sky-600 hover:text-white transition-all text-[11px]">Editar</button>
                                            <a href="{{ url_for('devolver', transaccion_id=alq[0]) }}" class="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 px-2 py-1 rounded font-bold hover:bg-emerald-500 hover:text-white transition-all text-[11px]">Retorno</a>
                                        </td>
                                    </tr>
                                    {% else %}
                                    <tr><td colspan="4" class="text-center py-6 text-slate-500">No se registran órdenes de alquiler activas.</td></tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <div class="space-y-6">
                    <div id="panel-opciones-equipo" class="bg-slate-900 border-2 border-dashed border-slate-800 p-5 rounded-xl text-center text-slate-500 text-xs flex flex-col justify-center h-48">
                        <span>💡 Haz clic en cualquier fila de la lista del inventario para ver las especificaciones técnicas completas y activar sus acciones comerciales o de soporte técnico.</span>
                    </div>

                    <div id="modulo-activo-equipo" class="hidden bg-slate-900 p-5 rounded-xl border border-indigo-500/30 shadow-2xl text-xs space-y-4">
                        <div class="flex justify-between items-center border-b border-slate-800 pb-2">
                            <span class="bg-indigo-600/20 text-indigo-400 px-2 py-0.5 rounded font-mono font-bold uppercase tracking-wider text-[9px]" id="info-badge-marca">DELL</span>
                            <button onclick="cerrarModuloEquipo()" class="text-slate-400 hover:text-white font-bold">✕</button>
                        </div>
                        
                        <div class="flex border-b border-slate-800 font-bold text-[11px]">
                            <button id="tab-btn-specs" onclick="cambiarPestana('specs')" class="w-1/3 pb-2 border-b-2 border-indigo-500 text-white">📋 Detalles</button>
                            <button id="tab-btn-renta" onclick="cambiarPestana('renta')" class="w-1/3 pb-2 border-b-2 border-transparent text-slate-400 hover:text-slate-200">📝 Despacho</button>
                            <button id="tab-btn-soporte" onclick="cambiarPestana('soporte')" class="w-1/3 pb-2 border-b-2 border-transparent text-slate-400 hover:text-slate-200">🛠️ Soporte</button>
                        </div>

                        <div id="tab-content-specs" class="space-y-3">
                            <div>
                                <span class="text-slate-400 block font-semibold text-[10px] uppercase">Ficha Técnica Base</span>
                                <p class="text-white font-bold text-sm" id="info-txt-nombre"></p>
                            </div>
                            <div class="grid grid-cols-2 gap-2 bg-slate-950 p-3 rounded-lg border border-slate-800">
                                <div>
                                    <span class="text-slate-400 block text-[9px] uppercase font-bold">Precio Alquiler</span>
                                    <span class="text-cyan-400 font-black text-sm font-mono" id="info-txt-precio-renta"></span>
                                </div>
                                <div>
                                    <span class="text-slate-400 block text-[9px] uppercase font-bold">Valor de Mercado</span>
                                    <span class="text-amber-400 font-black text-sm font-mono" id="info-txt-precio-real"></span>
                                </div>
                            </div>
                            <div class="bg-indigo-950/20 border border-indigo-900/40 p-2.5 rounded-lg text-indigo-300 text-[11px]">
                                ℹ️ <strong>Auditoría de Activos:</strong> El valor estimado del equipo en el mercado permite calcular el retorno de inversión corporativo (ROI).
                            </div>
                        </div>

                        <div id="tab-content-renta" class="hidden">
                            <form action="{{ url_for('procesar_salida') }}" method="POST" class="space-y-3">
                                <input type="hidden" name="equipo_id" id="form-action-id">
                                <div class="flex justify-between items-center bg-slate-950 p-2 rounded border border-slate-800">
                                    <span class="text-slate-400 font-semibold uppercase text-[10px]">Unidades Disponibles:</span>
                                    <strong class="text-emerald-400 font-mono text-sm" id="form-action-stock-label"></strong>
                                </div>
                                <div id="form-wrapper-cantidad">
                                    <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider text-[10px]">Cantidad a Despachar</label>
                                    <input type="number" name="cantidad" id="form-action-cantidad" min="1" value="1" oninput="recalcularPrecioAccion()" required class="w-full px-2 py-1.5 bg-slate-950 border border-slate-700 rounded-lg text-white font-mono text-center">
                                </div>
                                <div>
                                    <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider text-[10px]">Cliente / Razón Social</label>
                                    <input type="text" name="cliente" required placeholder="Ej: Importaciones SAC" class="w-full px-3 py-1.5 bg-slate-950 border border-slate-700 rounded-lg text-white">
                                </div>
                                <div>
                                    <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider text-[10px]">Teléfono de Enlace</label>
                                    <input type="tel" name="telefono_cliente" required placeholder="Ej: 987654321" class="w-full px-3 py-1.5 bg-slate-950 border border-slate-700 rounded-lg text-white">
                                </div>
                                <div class="grid grid-cols-2 gap-2">
                                    <div>
                                        <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider text-[9px]">Salida</label>
                                        <input type="date" name="fecha_inicio" id="form-action-f1" onchange="recalcularPrecioAccion()" required class="w-full px-2 py-1 bg-slate-950 border border-slate-700 rounded-lg text-white text-center font-mono text-[11px]">
                                    </div>
                                    <div>
                                        <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider text-[9px]">Devolución</label>
                                        <input type="date" name="fecha_fin" id="form-action-f2" onchange="recalcularPrecioAccion()" required class="w-full px-2 py-1 bg-slate-950 border border-slate-700 rounded-lg text-white text-center font-mono text-[11px]">
                                    </div>
                                </div>
                                <div>
                                    <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider text-[10px]">Costo Total Dinámico</label>
                                    <input type="number" step="0.01" name="precio" id="form-action-total" required class="w-full px-3 py-1.5 bg-slate-950 border border-slate-700 rounded-lg font-mono font-bold text-sm text-cyan-400">
                                </div>
                                <button type="submit" class="w-full py-2.5 bg-indigo-600 text-white font-bold rounded-lg uppercase tracking-wider hover:bg-indigo-500 transition-all shadow-md">Registrar Despacho Oficial</button>
                            </form>
                        </div>

                        <div id="tab-content-soporte" class="hidden py-4 text-center">
                            <span class="text-3xl block mb-2">🛠️</span>
                            <h4 class="text-white font-bold text-sm mb-1">Módulo de Revisión Técnica</h4>
                            <p class="text-slate-400 text-[11px] px-2 mb-4">Envía unidades de este lote al laboratorio por fallas o mantenimiento preventivo.</p>
                            <form action="{{ url_for('enviar_mantenimiento') }}" method="POST" class="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-3">
                                <input type="hidden" name="equipo_id" id="form-soporte-id">
                                <div class="flex justify-between items-center text-xs">
                                    <span class="text-slate-400 font-bold uppercase">Unidades Disp:</span>
                                    <strong class="text-emerald-400 font-mono text-sm" id="form-soporte-disp"></strong>
                                </div>
                                <div id="form-soporte-wrapper">
                                    <input type="number" name="cantidad" id="form-soporte-cantidad" min="1" required class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white font-mono text-center focus:border-amber-500" placeholder="Cant. a enviar">
                                </div>
                                <button type="submit" class="w-full py-2 bg-amber-600 hover:bg-amber-500 text-white font-bold rounded-lg transition-all shadow-lg text-xs">Trasladar al Taller Técnico</button>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div id="sec-mantenimiento" class="section-container hidden space-y-6">
            <div class="bg-slate-900 p-4 sm:p-6 rounded-xl border border-slate-800">
                <h2 class="text-base sm:text-lg font-bold text-white mb-1">🛠️ Laboratorio y Mantenimiento Técnico</h2>
                <p class="text-xs text-slate-400 mb-6">Equipos actualmente retirados del almacén central para revisión de hardware, actualización de software o reparación física.</p>
                <div class="overflow-x-auto rounded-lg border border-slate-800/50">
                    <table class="w-full text-left text-xs text-slate-300">
                        <thead class="text-slate-400 bg-slate-950 border-b border-slate-800 uppercase tracking-wider text-[10px]">
                            <tr>
                                <th class="py-3 px-4">Hardware en Reparación</th>
                                <th class="py-3 px-4 text-center">Unidades Afectadas</th>
                                <th class="py-3 px-4 text-center">Estado Logístico</th>
                                <th class="py-3 px-4 text-center">Acción de Retorno</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-800/40">
                            {% for eq in equipos_mantenimiento %}
                            <tr class="hover:bg-slate-800/20 transition-colors">
                                <td class="py-3 px-4 text-white font-semibold">{{ eq[1] }}</td>
                                <td class="py-3 px-4 text-center text-amber-400 font-mono font-bold">{{ eq[3] }} uds.</td>
                                <td class="py-3 px-4 text-center">
                                    <span class="text-amber-400 font-bold bg-amber-500/10 px-2 py-0.5 border border-amber-500/20 rounded text-[10px] whitespace-nowrap">En Laboratorio</span>
                                </td>
                                <td class="py-3 px-4 text-center">
                                    <form action="{{ url_for('retornar_mantenimiento') }}" method="POST" class="flex justify-center items-center space-x-2">
                                        <input type="hidden" name="equipo_id" value="{{ eq[0] }}">
                                        <input type="number" name="cantidad" min="1" max="{{ eq[3] }}" value="{{ eq[3] }}" required class="w-16 bg-slate-950 border border-slate-700 rounded text-center py-1 text-white font-mono">
                                        <button type="submit" class="bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1 rounded transition-all shadow-md font-bold text-[10px] whitespace-nowrap">✔ Terminar</button>
                                    </form>
                                </td>
                            </tr>
                            {% else %}
                            <tr><td colspan="4" class="text-center py-6 text-slate-500">El laboratorio técnico se encuentra vacío. Todos los equipos corporativos están operativos.</td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
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
                        <span class="text-xs font-bold text-slate-300 block text-center">Top 5 Clientes Estratégicos</span>
                        <div class="relative h-56 sm:h-64 w-full flex justify-center items-center"><canvas id="chartTopClientes"></canvas></div>
                    </div>
                    <div class="bg-slate-950 p-4 rounded-xl border border-slate-800 h-72 sm:h-80 flex flex-col justify-between">
                        <span class="text-xs font-bold text-slate-300 block text-center">Estructura Logística de Unidades</span>
                        <div class="relative h-56 sm:h-64 w-full flex justify-center items-center"><canvas id="chartStock"></canvas></div>
                    </div>
                </div>
            </div>
        </div>

        <div id="sec-clientes" class="section-container hidden space-y-6">
            <div class="bg-slate-900 p-4 sm:p-6 rounded-xl border border-slate-800">
                <h2 class="text-base sm:text-lg font-bold text-white mb-1">👥 Módulo CRM - Base de Datos Transaccional</h2>
                <p class="text-xs text-slate-400 mb-6">Auditoría permanente e histórica de las relaciones comerciales. Permite alteración manual con re-inyección de stock en activos.</p>
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
                                <th class="py-3 px-4 text-center">Acciones</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-800/40">
                            {% for hist in historial_completo %}
                            <tr class="hover:bg-slate-800/20 transition-colors">
                                <td class="py-3 px-4 text-white font-semibold">{{ hist[2] }}</td>
                                <td class="py-3 px-4 text-slate-400 font-mono">{{ hist[3] }}</td>
                                <td class="py-3 px-4 text-slate-300 font-mono text-[11px] max-w-[180px] truncate" title="{{ hist[1] }}">
                                    <span class="text-indigo-400 font-black">{{ hist[9] }}x</span> {{ hist[1] }}
                                </td>
                                <td class="py-3 px-4 text-center text-slate-400 font-mono whitespace-nowrap">{{ hist[4] }} al {{ hist[5] }}</td>
                                <td class="py-3 px-4 text-right font-bold text-cyan-400 font-mono whitespace-nowrap">S/. {{ "%.2f"|format(hist[6]) }}</td>
                                <td class="py-3 px-4 text-center whitespace-nowrap">
                                    {% if hist[8] == 1 %}
                                        <span class="text-amber-400 font-bold bg-amber-500/10 px-2.5 py-0.5 border border-amber-500/20 rounded text-[10px]">Activo</span>
                                    {% else %}
                                        <span class="text-emerald-400 font-bold bg-emerald-500/10 px-2.5 py-0.5 border border-emerald-500/20 rounded text-[10px]">Devuelto</span>
                                    {% endif %}
                                </td>
                                <td class="py-3 px-4 text-center flex justify-center space-x-2 whitespace-nowrap">
                                    <a href="{{ url_for('descargar_pdf', t_id=hist[0]) }}" target="_blank" class="bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 px-2 py-1 rounded font-bold hover:bg-indigo-600 hover:text-white transition-all text-[10px]">PDF</a>
                                    <button onclick="abrirModalEditHistorial('{{ hist[0] }}', '{{ hist[2] }}', '{{ hist[3] }}', '{{ hist[4] }}', '{{ hist[5] }}', '{{ hist[6] }}')" class="text-sky-400 hover:text-white font-bold bg-sky-500/10 px-2 py-1 rounded text-[10px] transition-all">Editar</button>
                                    <form action="{{ url_for('eliminar_historial', t_id=hist[0]) }}" method="POST" onsubmit="return confirm('¿Seguro que deseas ELIMINAR este registro del historial CRM? Esta acción es irreversible.');">
                                        <button type="submit" class="text-rose-400 hover:text-white hover:bg-rose-600 font-bold bg-rose-500/10 px-2 py-1 rounded text-[10px] transition-all">Borrar</button>
                                    </form>
                                </td>
                            </tr>
                            {% empty %}
                            <tr><td colspan="7" class="text-center py-6 text-slate-500">No se detectan registros comerciales en el CRM local.</td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

    </main>

    <div id="modal-edit-unidades" class="hidden fixed inset-0 bg-slate-950/80 z-50 flex items-center justify-center px-4 backdrop-blur-sm">
        <div class="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-sm p-6 shadow-2xl">
            <h3 class="text-white font-bold text-base mb-1">📝 Modificar Unidades del Contrato</h3>
            <p class="text-slate-400 text-[11px] mb-4 font-medium" id="edit-unidades-cliente-label"></p>
            <form action="{{ url_for('editar_unidades_transaccion') }}" method="POST" class="space-y-4 text-xs">
                <input type="hidden" name="transaccion_id" id="edit-unidades-id">
                <div>
                    <span class="text-slate-400 block mb-1 uppercase font-bold tracking-wider text-[10px]">Equipo Vinculado:</span>
                    <p class="text-white font-mono text-[11px] bg-slate-950 p-2.5 rounded border border-slate-800" id="edit-unidades-equipo-label"></p>
                </div>
                <div>
                    <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider text-[10px]">Corregir Unidades Solicitadas</label>
                    <input type="number" name="nueva_cantidad" id="edit-unidades-cantidad-input" min="1" required class="w-full text-center px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-lg font-bold text-cyan-400 font-mono">
                    <p class="text-slate-400 text-[10px] mt-1 text-center">💡 El stock del almacén se ajustará automáticamente.</p>
                </div>
                <div class="flex space-x-3 pt-2">
                    <button type="button" onclick="document.getElementById('modal-edit-unidades').classList.add('hidden')" class="w-1/2 py-2 bg-slate-800 hover:bg-slate-700 text-white font-bold rounded-lg">Cerrar</button>
                    <button type="submit" class="w-1/2 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-lg shadow-md">Guardar Ajuste</button>
                </div>
            </form>
        </div>
    </div>

    <div id="modal-edit-historial" class="hidden fixed inset-0 bg-slate-950/80 z-50 flex items-center justify-center px-4 backdrop-blur-sm overflow-y-auto py-10">
        <div class="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-md p-6 shadow-2xl">
            <h3 class="text-white font-bold text-lg mb-1">✏️ Editar Registro CRM</h3>
            <p class="text-slate-400 text-[11px] mb-5">Modifica los datos del cliente o la facturación del contrato.</p>
            <form action="{{ url_for('editar_historial') }}" method="POST" class="space-y-4 text-xs">
                <input type="hidden" name="transaccion_id" id="edit-hist-id">
                <div>
                    <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider text-[10px]">Cliente / Razón Social</label>
                    <input type="text" name="cliente" id="edit-hist-cliente" required class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white focus:border-indigo-500">
                </div>
                <div>
                    <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider text-[10px]">Contacto Celular</label>
                    <input type="tel" name="telefono_cliente" id="edit-hist-tel" required class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white focus:border-indigo-500">
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider text-[10px]">Fecha de Salida</label>
                        <input type="date" name="fecha_inicio" id="edit-hist-f1" required class="w-full px-2 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white font-mono text-center">
                    </div>
                    <div>
                        <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider text-[10px]">Fecha de Retorno</label>
                        <input type="date" name="fecha_fin" id="edit-hist-f2" required class="w-full px-2 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white font-mono text-center">
                    </div>
                </div>
                <div>
                    <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider text-[10px]">Precio Total Facturado (S/.)</label>
                    <input type="number" step="0.01" name="precio_total" id="edit-hist-precio" required class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg font-mono font-bold text-cyan-400 text-sm focus:border-indigo-500">
                </div>
                <div class="flex space-x-3 pt-4 border-t border-slate-800">
                    <button type="button" onclick="document.getElementById('modal-edit-historial').classList.add('hidden')" class="w-1/2 py-2.5 bg-slate-800 hover:bg-slate-700 text-white font-bold rounded-lg transition-all">Cancelar</button>
                    <button type="submit" class="w-1/2 py-2.5 bg-sky-600 hover:bg-sky-500 text-white font-bold rounded-lg transition-all shadow-lg">Actualizar Ficha</button>
                </div>
            </form>
        </div>
    </div>

    <div id="modal-add" class="hidden fixed inset-0 bg-slate-950/80 z-50 flex items-center justify-center px-4 backdrop-blur-sm">
        <div class="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-md p-6 shadow-2xl">
            <h3 class="text-white font-bold text-lg mb-1">➕ Añadir Nuevo Hardware</h3>
            <form action="{{ url_for('agregar_equipo') }}" method="POST" class="space-y-4 text-xs mt-4">
                <div>
                    <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider">Especificaciones Técnicas</label>
                    <input type="text" name="especificaciones" required class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white">
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider">Marca</label>
                        <select name="marca" required class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white">
                            <option value="DELL">DELL</option><option value="LENOVO">LENOVO</option><option value="HP">HP</option><option value="OTRA">OTRA</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider">Stock Inicial</label>
                        <input type="number" name="stock" min="1" required class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white text-center font-mono">
                    </div>
                </div>
                <div>
                    <label class="block text-slate-400 mb-1 font-semibold uppercase tracking-wider">Tarifa Semanal (S/.)</label>
                    <input type="number" step="0.01" name="precio" min="1" required class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-indigo-400 font-bold font-mono">
                </div>
                <div class="flex space-x-3 pt-4">
                    <button type="button" onclick="document.getElementById('modal-add').classList.add('hidden')" class="w-1/2 py-2.5 bg-slate-800 text-white font-bold rounded-lg">Cancelar</button>
                    <button type="submit" class="w-1/2 py-2.5 bg-emerald-600 text-white font-bold rounded-lg">Guardar Equipo</button>
                </div>
            </form>
        </div>
    </div>

    <script>
    let activeTarifaSugerida = 0.0;

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

    function abrirModuloEquipo(id, nombre, marca, stockDisp, stockTot, precioRenta, precioReal) {
        document.getElementById('panel-opciones-equipo').classList.add('hidden');
        const modulo = document.getElementById('modulo-activo-equipo');
        modulo.classList.remove('hidden');

        document.getElementById('info-badge-marca').innerText = marca;
        document.getElementById('info-txt-nombre').innerText = nombre;
        document.getElementById('info-txt-precio-renta').innerText = 'S/. ' + parseFloat(precioRenta).toFixed(2);
        document.getElementById('info-txt-precio-real').innerText = 'S/. ' + parseFloat(precioReal).toFixed(2);

        document.getElementById('form-action-id').value = id;
        document.getElementById('form-soporte-id').value = id;
        document.getElementById('form-action-stock-label').innerText = stockDisp + ' / ' + stockTot + ' uds.';
        document.getElementById('form-soporte-disp').innerText = stockDisp + ' uds.';
        
        document.getElementById('form-action-cantidad').value = 1;
        document.getElementById('form-action-cantidad').max = parseInt(stockDisp);
        document.getElementById('form-soporte-cantidad').value = 1;
        document.getElementById('form-soporte-cantidad').max = parseInt(stockDisp);
        
        if (parseInt(stockDisp) <= 0) {
            document.getElementById('form-wrapper-cantidad').style.display = 'none';
            document.getElementById('form-soporte-wrapper').style.display = 'none';
        } else {
            document.getElementById('form-wrapper-cantidad').style.display = 'block';
            document.getElementById('form-soporte-wrapper').style.display = 'block';
        }

        activeTarifaSugerida = parseFloat(precioRenta);
        recalcularPrecioAccion();
        cambiarPestana('specs');
    }

    function cerrarModuloEquipo() {
        document.getElementById('modulo-activo-equipo').classList.add('hidden');
        document.getElementById('panel-opciones-equipo').classList.remove('hidden');
    }

    function cambiarPestana(target) {
        ['specs', 'renta', 'soporte'].forEach(p => {
            document.getElementById('tab-content-' + p).classList.add('hidden');
            document.getElementById('tab-btn-' + p).classList.remove('border-indigo-500', 'text-white');
            document.getElementById('tab-btn-' + p).classList.add('border-transparent', 'text-slate-400');
        });
        document.getElementById('tab-content-' + target).classList.remove('hidden');
        document.getElementById('tab-btn-' + target).classList.remove('border-transparent', 'text-slate-400');
        document.getElementById('tab-btn-' + target).classList.add('border-indigo-500', 'text-white');
    }

    function recalcularPrecioAccion() {
        const cant = parseInt(document.getElementById("form-action-cantidad").value) || 1;
        const inputPrecio = document.getElementById("form-action-total");
        const f1 = document.getElementById("form-action-f1").value;
        const f2 = document.getElementById("form-action-f2").value;
        let semanas = 1;
        if (f1 && f2) {
            const dias = Math.ceil((new Date(f2) - new Date(f1)) / (1000 * 60 * 60 * 24));
            if (dias > 0) semanas = Math.ceil(dias / 7);
        }
        inputPrecio.value = (activeTarifaSugerida * cant * semanas).toFixed(2);
    }

    function abrirModalEdicionUnidades(id, cliente, cantidadActual, equipoNombre) {
        document.getElementById('modal-edit-unidades').classList.remove('hidden');
        document.getElementById('edit-unidades-id').value = id;
        document.getElementById('edit-unidades-cliente-label').innerText = 'Modificando la orden del cliente: ' + cliente;
        document.getElementById('edit-unidades-equipo-label').innerText = equipoNombre;
        document.getElementById('edit-unidades-cantidad-input').value = cantidadActual;
    }

    function abrirModalEditHistorial(id, cliente, tel, f_ini, f_fin, precio) {
        document.getElementById('edit-hist-id').value = id;
        document.getElementById('edit-hist-cliente').value = cliente;
        document.getElementById('edit-hist-tel').value = tel;
        document.getElementById('edit-hist-precio').value = parseFloat(precio).toFixed(2);

        function formatoHtml(fecha) {
            if(!fecha || !fecha.includes('/')) return fecha;
            const partes = fecha.split('/');
            return `${partes[2]}-${partes[1]}-${partes[0]}`;
        }
        document.getElementById('edit-hist-f1').value = formatoHtml(f_ini);
        document.getElementById('edit-hist-f2').value = formatoHtml(f_fin);
        document.getElementById('modal-edit-historial').classList.remove('hidden');
    }

    function buscarEquipo() {
        var input = document.getElementById("inputBuscar");
        var filter = input.value.toUpperCase();
        var table = document.getElementById("tablaEquipos");
        var tr = table.getElementsByTagName("tr");
        for (var i = 1; i < tr.length; i++) {
            var tdNombre = tr[i].getElementsByTagName("td")[0];
            if (tdNombre) {
                tr[i].style.display = (tdNombre.innerText.toUpperCase().indexOf(filter) > -1) ? "" : "none";
            }
        }
    }

    const topClientesLabels = {{ stats.top_clientes_labels|tojson }};
    const topClientesData = {{ stats.top_clientes_data|tojson }};
    const ctxClientes = document.getElementById('chartTopClientes').getContext('2d');
    new Chart(ctxClientes, {
        type: 'bar', data: { labels: topClientesLabels, datasets: [{ data: topClientesData, backgroundColor: 'rgba(56, 189, 248, 0.6)', borderColor: '#38bdf8', borderWidth: 1, borderRadius: 5 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: '#1e293b' }, ticks: { color: '#94a3b8', font: { size: 9 } } }, x: { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 9 } } } } }
    });

    const ctxStock = document.getElementById('chartStock').getContext('2d');
    new Chart(ctxStock, {
        type: 'doughnut', data: { labels: ['Uds en Almacén', 'Uds en Campo'], datasets: [{ data: [{{ graph_data.stock_disp }}, {{ graph_data.stock_alqu }}], backgroundColor: ['rgba(52, 211, 153, 0.6)', 'rgba(99, 102, 241, 0.6)'], borderColor: ['#34d399', '#6366f1'], borderWidth: 1 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 } } } } }
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
    if 'usuario_id' in session: return redirect(url_for('dashboard'))
    return render_template_string(VISTA_LOGIN)

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, nombre FROM usuarios WHERE username=%s AND password=%s", (username, password))
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
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM usuarios WHERE username=%s OR email=%s", (username_generado, email))
        if cursor.fetchone():
            conn.close()
            flash("El usuario o correo electrónico ya existen.")
            return render_template_string(VISTA_REGISTRO)
        conn.close()
        session['temp_registro'] = {'nombre': nombre, 'username': username_generado, 'telefono': telefono, 'email': email, 'password': password}
        return redirect(url_for('verificar_codigo'))
    return render_template_string(VISTA_REGISTRO)

@app.route('/verificar-codigo', methods=['GET', 'POST'])
def verificar_codigo():
    if 'temp_registro' not in session: return redirect(url_for('registro'))
    if request.method == 'POST':
        codigo_ingresado = request.form['codigo_ingresado'].strip()
        datos_temp = session['temp_registro']
        if codigo_ingresado in CREDENCIALES_VALIDAS:
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute('INSERT INTO usuarios (username, password, nombre, email, telefono) VALUES (%s, %s, %s, %s, %s)',
                               (datos_temp['username'], datos_temp['password'], datos_temp['nombre'], datos_temp['email'], datos_temp['telefono']))
                conn.commit()
                u, p = datos_temp['username'], datos_temp['password']
                session.pop('temp_registro', None)
                return render_template_string(VISTA_EXITO, username=u, password=p)
            except IntegrityError:
                flash("Error de duplicidad. Verifique sus datos.")
            finally:
                conn.close()
        else:
            flash("Token de trabajador inválido o no autorizado.")
    return render_template_string(VISTA_VERIFICACION)

@app.route('/cancelar-registro')
def cancelar_registro():
    session.pop('temp_registro', None)
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session: return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, marca, stock_total, stock_disponible, precio_alquiler, precio_mercado FROM equipos ORDER BY marca, nombre")
    equipos = cursor.fetchall()
    
    cursor.execute("SELECT id, nombre, marca, stock_mantenimiento FROM equipos WHERE stock_mantenimiento > 0 ORDER BY marca")
    equipos_mantenimiento = cursor.fetchall()
    
    cursor.execute("SELECT t.id, e.nombre, t.cliente, t.fecha_inicio, t.fecha_fin, t.precio_total, t.cantidad FROM transacciones t JOIN equipos e ON t.equipo_id = e.id WHERE t.activo = 1 ORDER BY t.id DESC")
    transacciones_activas = cursor.fetchall()
    
    cursor.execute("SELECT t.id, e.nombre, t.cliente, t.telefono_cliente, t.fecha_inicio, t.fecha_fin, t.precio_total, 'Alquiler', t.activo, t.cantidad FROM transacciones t JOIN equipos e ON t.equipo_id = e.id ORDER BY t.id DESC")
    historial_completo = cursor.fetchall()
    
    cursor.execute("SELECT nombre, email, telefono FROM usuarios WHERE id=%s", (session['usuario_id'],))
    perfil = cursor.fetchone()
    perfil_dict = {'nombre': perfil[0], 'email': perfil[1], 'telefono': perfil[2]} if perfil else {'nombre': session['nombre'], 'email': '-', 'telefono': '-'}

    alertas_devolucion = []
    for alq in transacciones_activas:
        try:
            f_fin = datetime.strptime(alq[4], "%d/%m/%Y")
            dias_restantes = (f_fin - datetime.now()).days + 1
            if dias_restantes < 0:
                alertas_devolucion.append({'cliente': alq[2], 'equipo': alq[1], 'telefono': historial_completo[0][3], 'mensaje': f"se encuentra VENCIDO por {abs(dias_restantes)} días. Requiere retorno inmediato"})
            elif dias_restantes <= 1:
                alertas_devolucion.append({'cliente': alq[2], 'equipo': alq[1], 'telefono': historial_completo[0][3], 'mensaje': "vence MAÑANA. Confirmar logística de recojo"})
        except Exception:
            pass

    cursor.execute("SELECT COUNT(*), SUM(stock_disponible), SUM(stock_total) FROM equipos")
    res_eq = cursor.fetchone()
    total_modelos, stock_disp, stock_total_corp = int(res_eq[0] or 0), int(res_eq[1] or 0), int(res_eq[2] or 0)
    stock_alqu = stock_total_corp - stock_disp
    tasa_ocupacion = (stock_alqu / stock_total_corp * 100) if stock_total_corp > 0 else 0.0

    cursor.execute("SELECT COUNT(*), SUM(precio_total), AVG(precio_total), COUNT(DISTINCT cliente) FROM transacciones")
    res_trans = cursor.fetchone()
    total_transacciones, ganancias_totales = int(res_trans[0] or 0), float(res_trans[1] or 0.0)
    ticket_promedio, clientes_unicos = float(res_trans[2] or 0.0), int(res_trans[3] or 0)

    cursor.execute("SELECT cliente, SUM(precio_total) FROM transacciones GROUP BY cliente ORDER BY SUM(precio_total) DESC LIMIT 5")
    res_top = cursor.fetchall()
    top_clientes_labels = [r[0] for r in res_top] or ["Sin Transacciones"]
    top_clientes_data = [float(r[1]) for r in res_top] or [0]

    stats = {
        'total_modelos': total_modelos, 'unidades_disponibles': stock_disp, 'unidades_totales': stock_total_corp, 'unidades_alquiladas': stock_alqu, 'tasa_ocupacion': tasa_ocupacion, 'total_transacciones': total_transacciones,
        'ganancias_totales': ganancias_totales, 'ticket_promedio': ticket_promedio, 'clientes_unicos': clientes_unicos, 'top_clientes_labels': top_clientes_labels, 'top_clientes_data': top_clientes_data
    }
    graph_data = {'stock_disp': stock_disp, 'stock_alqu': stock_alqu}
    conn.close()
    
    return render_template_string(VISTA_DASHBOARD, equipos=equipos, equipos_mantenimiento=equipos_mantenimiento, transacciones_activas=transacciones_activas, historial_completo=historial_completo, perfil=perfil_dict, stats=stats, graph_data=graph_data, alertas_devolucion=alertas_devolucion)

# ==========================================
# RUTAS DE PDF Y MANTENIMIENTO TÉCNICO
# ==========================================
@app.route('/descargar-pdf/<int:t_id>')
def descargar_pdf(t_id):
    if 'usuario_id' not in session: return redirect(url_for('index'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT t.cliente, t.telefono_cliente, t.fecha_inicio, t.fecha_fin, t.cantidad, t.precio_total, e.nombre, e.marca FROM transacciones t JOIN equipos e ON t.equipo_id = e.id WHERE t.id=%s", (t_id,))
    res = cursor.fetchone()
    conn.close()
    
    if not res: return redirect(url_for('dashboard'))
    cliente, tel, f_ini, f_fin, cant, precio, eq_nombre, eq_marca = res

    pdf = FPDF()
    pdf.add_page()
    
    # Membrete Empresarial 
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(50, 50, 120)
    pdf.cell(0, 10, txt="SISTEMA ERP - DIVISION DE ACTIVOS TECNOLOGICOS", ln=True, align='C')
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, txt="CONTRATO OFICIAL DE ARRENDAMIENTO", ln=True, align='C')
    pdf.ln(5)

    # Datos Generales
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(50, 8, txt=" Nro. Operacion:", border=1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 8, txt=f" #ERP-{t_id:05d}", border=1, ln=True)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(50, 8, txt=" Cliente Registrado:", border=1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 8, txt=f" {cliente}", border=1, ln=True)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(50, 8, txt=" Contacto:", border=1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 8, txt=f" {tel}", border=1, ln=True)
    pdf.ln(8)

    # Tabla de Equipos
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(120, 8, txt="Equipo / Hardware Asignado", border=1, align='C')
    pdf.cell(30, 8, txt="Cantidad", border=1, align='C')
    pdf.cell(40, 8, txt="Costo Total", border=1, align='C', ln=True)
    
    pdf.set_font('Arial', '', 9)
    pdf.cell(120, 8, txt=f" {eq_marca} - {eq_nombre}", border=1)
    pdf.cell(30, 8, txt=f"{cant} uds.", border=1, align='C')
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(40, 8, txt=f"S/. {precio:.2f}", border=1, align='C', ln=True)
    pdf.ln(10)

    # Condiciones
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 8, txt=f"Vigencia del Contrato: Desde el {f_ini} hasta el {f_fin}.", ln=True)
    pdf.cell(0, 8, txt="Este documento sirve como constancia de recepcion de los equipos en optimas condiciones de hardware.", ln=True)
    
    pdf.ln(30)
    pdf.cell(90, 8, txt="_________________________________", align='C')
    pdf.cell(10, 8, txt="")
    pdf.cell(90, 8, txt="_________________________________", align='C', ln=True)
    pdf.cell(90, 8, txt="Firma Autorizada ERP", align='C')
    pdf.cell(10, 8, txt="")
    pdf.cell(90, 8, txt="Firma de Conformidad Cliente", align='C', ln=True)

    pdf_bytes = pdf.output(dest='S').encode('latin1')
    response = Response(pdf_bytes, mimetype="application/pdf")
    response.headers['Content-Disposition'] = f"attachment;filename=Contrato_ERP_00{t_id}.pdf"
    return response

@app.route('/enviar-mantenimiento', methods=['POST'])
def enviar_mantenimiento():
    if 'usuario_id' not in session: return redirect(url_for('index'))
    eq_id = int(request.form['equipo_id'])
    cant = int(request.form['cantidad'])
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT stock_disponible FROM equipos WHERE id=%s", (eq_id,))
    disp = cursor.fetchone()[0]
    if disp >= cant:
        cursor.execute("UPDATE equipos SET stock_disponible = stock_disponible - %s, stock_mantenimiento = stock_mantenimiento + %s WHERE id=%s", (cant, cant, eq_id))
        conn.commit()
        flash(f"🛠️ {cant} unidades enviadas al laboratorio de mantenimiento técnico.")
    else:
        flash("❌ Error: No hay suficientes unidades disponibles para mantenimiento.")
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/retornar-mantenimiento', methods=['POST'])
def retornar_mantenimiento():
    if 'usuario_id' not in session: return redirect(url_for('index'))
    eq_id = int(request.form['equipo_id'])
    cant = int(request.form['cantidad'])
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT stock_mantenimiento FROM equipos WHERE id=%s", (eq_id,))
    mant = cursor.fetchone()[0]
    if mant >= cant:
        cursor.execute("UPDATE equipos SET stock_mantenimiento = stock_mantenimiento - %s, stock_disponible = stock_disponible + %s WHERE id=%s", (cant, cant, eq_id))
        conn.commit()
        flash(f"✅ {cant} unidades reparadas y devueltas al almacén central.")
    conn.close()
    return redirect(url_for('dashboard'))

# ==========================================
# RUTAS ESTÁNDAR 
# ==========================================
@app.route('/editar-historial', methods=['POST'])
def editar_historial():
    if 'usuario_id' not in session: return redirect(url_for('index'))
    t_id = int(request.form['transaccion_id'])
    cliente, telefono = request.form['cliente'], request.form['telefono_cliente']
    f_inicio_raw, f_fin_raw = request.form['fecha_inicio'], request.form['fecha_fin']
    precio = float(request.form['precio_total'])
    try:
        f_inicio = datetime.strptime(f_inicio_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
        f_fin = datetime.strptime(f_fin_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        f_inicio, f_fin = f_inicio_raw, f_fin_raw

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE transacciones SET cliente=%s, telefono_cliente=%s, fecha_inicio=%s, fecha_fin=%s, precio_total=%s WHERE id=%s",
                   (cliente, telefono, f_inicio, f_fin, precio, t_id))
    conn.commit()
    conn.close()
    flash("✅ Registro CRM modificado exitosamente.")
    return redirect(url_for('dashboard'))

@app.route('/eliminar-historial/<int:t_id>', methods=['POST'])
def eliminar_historial(t_id):
    if 'usuario_id' not in session: return redirect(url_for('index'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT equipo_id, cantidad, activo FROM transacciones WHERE id=%s", (t_id,))
    res = cursor.fetchone()
    if res:
        eq_id, cant, activo = res
        if activo == 1:
            cursor.execute("UPDATE equipos SET stock_disponible = stock_disponible + %s WHERE id=%s", (cant, eq_id))
        cursor.execute("DELETE FROM transacciones WHERE id=%s", (t_id,))
        conn.commit()
        flash("🗑️ Registro del historial CRM eliminado y purgado.")
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/editar-unidades-transaccion', methods=['POST'])
def editar_unidades_transaccion():
    if 'usuario_id' not in session: return redirect(url_for('index'))
    t_id = int(request.form['transaccion_id'])
    nueva_cantidad = int(request.form['nueva_cantidad'])
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT equipo_id, cantidad, precio_total FROM transacciones WHERE id=%s", (t_id,))
    transaccion = cursor.fetchone()
    if transaccion:
        eq_id, cantidad_vieja, precio_total_viejo = transaccion
        diferencia_unidades = nueva_cantidad - cantidad_vieja
        cursor.execute("SELECT stock_disponible FROM equipos WHERE id=%s", (eq_id,))
        stock_disp = cursor.fetchone()[0]
        if diferencia_unidades > stock_disp:
            flash(f"❌ Ajuste denegado: El almacén central no cuenta con unidades libres suficientes.")
        else:
            nuevo_precio_total = (float(precio_total_viejo) / cantidad_vieja) * nueva_cantidad
            cursor.execute("UPDATE transacciones SET cantidad=%s, precio_total=%s WHERE id=%s", (nueva_cantidad, nuevo_precio_total, t_id))
            cursor.execute("UPDATE equipos SET stock_disponible = stock_disponible - %s WHERE id=%s", (diferencia_unidades, eq_id))
            conn.commit()
            flash("✅ Unidades de contrato modificadas.")
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/exportar-inventario')
def exportar_inventario():
    if 'usuario_id' not in session: return redirect(url_for('index'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nombre, marca, stock_total, stock_disponible, precio_alquiler, precio_mercado FROM equipos ORDER BY marca, nombre")
    equipos = cursor.fetchall()
    conn.close()
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Especificaciones Tecnicas', 'Marca', 'Stock Empresa', 'Stock en Almacen', 'Tarifa Semanal (S/.)', 'Valor Real de Mercado (S/.)'])
    for eq in equipos: writer.writerow([eq[0], eq[1], eq[2], eq[3], f"{eq[4]:.2f}", f"{eq[5]:.2f}"])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename=Inventario_{datetime.now().strftime('%d-%m-%Y')}.csv"})

@app.route('/agregar-equipo', methods=['POST'])
def agregar_equipo():
    if 'usuario_id' not in session: return redirect(url_for('index'))
    especificaciones, marca = request.form['especificaciones'], request.form['marca']
    stock, precio = int(request.form['stock']), float(request.form['precio'])
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO equipos (nombre, marca, stock_total, stock_disponible, precio_alquiler, precio_mercado) VALUES (%s, %s, %s, %s, %s, %s)",
                   (especificaciones, marca.upper(), stock, stock, precio, precio * 50.0))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/eliminar-equipo/<int:equipo_id>', methods=['POST'])
def eliminar_equipo(equipo_id):
    if 'usuario_id' not in session: return redirect(url_for('index'))
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM equipos WHERE id=%s", (equipo_id,))
        conn.commit()
        flash("🗑️ Equipo eliminado del catálogo correctamente.")
    except IntegrityError:
        flash("⚠️ No puedes eliminar este equipo porque tiene un historial de alquileres.")
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/procesar-salida', methods=['POST'])
def procesar_salida():
    if 'usuario_id' not in session: return redirect(url_for('index'))
    equipo_id, cantidad = int(request.form['equipo_id']), int(request.form.get('cantidad', 1))
    cliente, telefono_cliente = request.form['cliente'], request.form['telefono_cliente']
    f_inicio_raw, f_fin_raw, precio = request.form['fecha_inicio'], request.form['fecha_fin'], float(request.form['precio'])
    try:
        f_inicio, f_fin = datetime.strptime(f_inicio_raw, "%Y-%m-%d").strftime("%d/%m/%Y"), datetime.strptime(f_fin_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        f_inicio, f_fin = f_inicio_raw, f_fin_raw
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT stock_disponible FROM equipos WHERE id=%s", (equipo_id,))
    stock_actual = cursor.fetchone()
    if stock_actual and stock_actual[0] >= cantidad:
        cursor.execute("UPDATE equipos SET stock_disponible = stock_disponible - %s WHERE id=%s", (cantidad, equipo_id))
        cursor.execute("INSERT INTO transacciones (equipo_id, cliente, telefono_cliente, fecha_inicio, fecha_fin, cantidad, precio_total, activo) VALUES (%s, %s, %s, %s, %s, %s, %s, 1)", 
                       (equipo_id, cliente, telefono_cliente, f_inicio, f_fin, cantidad, precio))
        conn.commit()
        flash(f"Salida registrada: {cantidad} unidades arrendadas al cliente {cliente}.")
    else:
        flash(f"Error: Stock insuficiente.")
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/devolver/<int:transaccion_id>')
def devolver(transaccion_id):
    if 'usuario_id' not in session: return redirect(url_for('index'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT equipo_id, cantidad FROM transacciones WHERE id=%s", (transaccion_id,))
    res = cursor.fetchone()
    if res:
        eq_id, cant = res
        cursor.execute("UPDATE transacciones SET activo = 0 WHERE id=%s", (transaccion_id,))
        cursor.execute("UPDATE equipos SET stock_disponible = stock_disponible + %s WHERE id=%s", (cant, eq_id))
        conn.commit()
        flash(f"Retorno confirmado. {cant} unidades reintegradas.")
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

try:
    init_db()
except Exception as e:
    print(f"[CRÍTICO] Error al inicializar: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))