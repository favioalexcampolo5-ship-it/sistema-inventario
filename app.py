from flask import Flask, render_template_string, request, redirect, url_for, session, flash
import sqlite3
import random
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
DATABASE = 'inventario.db'

EXCEL_FILENAME = "20260630 Inventario de laptops TADEEM.xlsx"
CSV_FILENAME = "20260630 Inventario de laptops TADEEM.xlsx - TECNICA.csv"

CREDENCIALES_VALIDAS = [
    "223476", "115982", "334812", "449201", "556172",
    "668394", "772105", "883940", "992813", "123456",
    "654321", "789123", "456789", "987654", "246810"
]

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY,
        usuario TEXT UNIQUE NOT NULL,
        contraseña TEXT NOT NULL,
        email TEXT NOT NULL,
        es_trabajador INTEGER DEFAULT 0,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS laptops (
        id INTEGER PRIMARY KEY,
        codigo TEXT UNIQUE NOT NULL,
        marca TEXT NOT NULL,
        modelo TEXT NOT NULL,
        procesador TEXT,
        ram TEXT,
        almacenamiento TEXT,
        precio_compra REAL,
        estado TEXT DEFAULT 'Disponible',
        fecha_adquisicion TEXT,
        observaciones TEXT,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS alquileres (
        id INTEGER PRIMARY KEY,
        id_laptop INTEGER,
        cliente_nombre TEXT,
        cliente_email TEXT,
        cliente_telefono TEXT,
        fecha_inicio TEXT,
        fecha_fin TEXT,
        precio_total REAL,
        estado TEXT DEFAULT 'Activo',
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (id_laptop) REFERENCES laptops(id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ventas (
        id INTEGER PRIMARY KEY,
        id_laptop INTEGER,
        cliente_nombre TEXT,
        cliente_email TEXT,
        precio_venta REAL,
        fecha_venta TEXT,
        observaciones TEXT,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (id_laptop) REFERENCES laptops(id)
    )
    ''')
    
    # Insertar admin por defecto si no existe
    try:
        cursor.execute("INSERT INTO usuarios (usuario, contraseña, email, es_trabajador) VALUES (?, ?, ?, ?)",
                      ("admin", "admin123", "admin@local", 1))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    
    conn.close()

# Inicializar BD al arrancar la aplicación
init_db()

# ==========================================
# PLANTILLAS DE DISEÑO ADAPTATIVO (UI SPA)
# ==========================================

VISTA_LOGIN = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sistema de Inventario - Login</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .contenedor-login {
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 400px;
            width: 100%;
            padding: 40px;
        }
        
        .logo {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .logo h1 {
            color: #667eea;
            font-size: 28px;
            margin-bottom: 5px;
        }
        
        .logo p {
            color: #666;
            font-size: 14px;
        }
        
        .formulario {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .grupo-form {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        
        label {
            color: #333;
            font-weight: 500;
            font-size: 14px;
        }
        
        input {
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            transition: all 0.3s;
        }
        
        input:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        button {
            padding: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 14px;
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        
        .enlace-registro {
            text-align: center;
            margin-top: 20px;
        }
        
        .enlace-registro a {
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
            font-size: 14px;
        }
        
        .enlace-registro a:hover {
            text-decoration: underline;
        }
        
        .alerta {
            padding: 12px;
            background: #fee;
            color: #c33;
            border-radius: 8px;
            font-size: 14px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="contenedor-login">
        <div class="logo">
            <h1>📱 Sistema ERP</h1>
            <p>Gestión de Inventario y Alquiler</p>
        </div>
        
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for message in messages %}
                    <div class="alerta">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <form method="POST" class="formulario">
            <div class="grupo-form">
                <label>Usuario</label>
                <input type="text" name="usuario" required>
            </div>
            
            <div class="grupo-form">
                <label>Contraseña</label>
                <input type="password" name="contraseña" required>
            </div>
            
            <button type="submit">Iniciar Sesión</button>
        </form>
        
        <div class="enlace-registro">
            ¿No tienes cuenta? <a href="/registro">Registrarse</a>
        </div>
    </div>
</body>
</html>
"""

VISTA_REGISTRO = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sistema de Inventario - Registro</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .contenedor-registro {
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 400px;
            width: 100%;
            padding: 40px;
        }
        
        .logo {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .logo h1 {
            color: #667eea;
            font-size: 28px;
            margin-bottom: 5px;
        }
        
        .logo p {
            color: #666;
            font-size: 14px;
        }
        
        .formulario {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .grupo-form {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        
        label {
            color: #333;
            font-weight: 500;
            font-size: 14px;
        }
        
        input {
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            transition: all 0.3s;
        }
        
        input:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        button {
            padding: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 14px;
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        
        .enlace-login {
            text-align: center;
            margin-top: 20px;
        }
        
        .enlace-login a {
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
            font-size: 14px;
        }
        
        .enlace-login a:hover {
            text-decoration: underline;
        }
        
        .alerta {
            padding: 12px;
            background: #fee;
            color: #c33;
            border-radius: 8px;
            font-size: 14px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="contenedor-registro">
        <div class="logo">
            <h1>📱 Sistema ERP</h1>
            <p>Crear Nueva Cuenta</p>
        </div>
        
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for message in messages %}
                    <div class="alerta">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <form method="POST" class="formulario">
            <div class="grupo-form">
                <label>Usuario</label>
                <input type="text" name="usuario" required>
            </div>
            
            <div class="grupo-form">
                <label>Email</label>
                <input type="email" name="email" required>
            </div>
            
            <div class="grupo-form">
                <label>Contraseña</label>
                <input type="password" name="contraseña" required>
            </div>
            
            <div class="grupo-form">
                <label>Confirmar Contraseña</label>
                <input type="password" name="confirmar_contraseña" required>
            </div>
            
            <button type="submit">Registrarse</button>
        </form>
        
        <div class="enlace-login">
            ¿Ya tienes cuenta? <a href="/login">Iniciar Sesión</a>
        </div>
    </div>
</body>
</html>
"""

VISTA_VALIDAR_TRABAJADOR = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Validar Identidad de Trabajador</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .contenedor {
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 400px;
            width: 100%;
            padding: 40px;
        }
        
        .logo {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .logo h1 {
            color: #667eea;
            font-size: 28px;
            margin-bottom: 5px;
        }
        
        .logo p {
            color: #666;
            font-size: 14px;
        }
        
        .info {
            background: #f0f4ff;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #667eea;
        }
        
        .info p {
            color: #333;
            font-size: 14px;
            line-height: 1.5;
        }
        
        .formulario {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .grupo-form {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        
        label {
            color: #333;
            font-weight: 500;
            font-size: 14px;
        }
        
        input {
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            transition: all 0.3s;
        }
        
        input:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        button {
            padding: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 14px;
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        
        .alerta {
            padding: 12px;
            background: #fee;
            color: #c33;
            border-radius: 8px;
            font-size: 14px;
            margin-bottom: 20px;
        }
        
        .exito {
            padding: 12px;
            background: #efe;
            color: #3c3;
            border-radius: 8px;
            font-size: 14px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="contenedor">
        <div class="logo">
            <h1>✅ Validar Identidad</h1>
            <p>Ingresa tu Código de Trabajador</p>
        </div>
        
        <div class="info">
            <p><strong>{{ usuario }}</strong></p>
            <p>Para completar tu registro, ingresa el código de trabajador que te proporcionó tu administrador.</p>
        </div>
        
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for message in messages %}
                    <div class="alerta">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <form method="POST" class="formulario">
            <div class="grupo-form">
                <label>Código de Trabajador</label>
                <input type="text" name="codigo_trabajador" placeholder="Ej: 223476" required autofocus>
            </div>
            
            <button type="submit">Validar Código</button>
        </form>
    </div>
</body>
</html>
"""

VISTA_DASHBOARD = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Sistema ERP</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #f5f7fa;
            padding: 20px;
        }
        
        .header {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 {
            color: #333;
            font-size: 24px;
        }
        
        .header p {
            color: #666;
            font-size: 14px;
        }
        
        .logout-btn {
            padding: 10px 20px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            text-decoration: none;
        }
        
        .logout-btn:hover {
            background: #764ba2;
        }
        
        .tarjetas {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .tarjeta {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            text-align: center;
        }
        
        .tarjeta h2 {
            color: #667eea;
            font-size: 32px;
            margin-bottom: 10px;
        }
        
        .tarjeta p {
            color: #666;
            font-size: 14px;
        }
        
        .menu {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        
        .boton-menu {
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            text-decoration: none;
            display: block;
            text-align: center;
        }
        
        .boton-menu:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>📱 Sistema ERP</h1>
            <p>¡Bienvenido, {{ usuario }}!</p>
        </div>
        <a href="/logout" class="logout-btn">Cerrar Sesión</a>
    </div>
    
    <div class="tarjetas">
        <div class="tarjeta">
            <h2>📊</h2>
            <p>Dashboard de Control</p>
        </div>
        <div class="tarjeta">
            <h2>💻</h2>
            <p>Gestión de Laptops</p>
        </div>
        <div class="tarjeta">
            <h2>👥</h2>
            <p>Clientes y Alquileres</p>
        </div>
    </div>
    
    <h2 style="margin-bottom: 15px;">Opciones Disponibles</h2>
    <div class="menu">
        <a href="/agregar-laptop" class="boton-menu">➕ Agregar Laptop</a>
        <a href="/ver-laptops" class="boton-menu">📋 Ver Inventario</a>
        <a href="/perfil" class="boton-menu">👤 Mi Perfil</a>
    </div>
</body>
</html>
"""

# ==========================================
# RUTAS DE LA APLICACIÓN
# ==========================================

@app.route('/')
def index():
    if 'usuario' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        contraseña = request.form.get('contraseña')
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT id, usuario, es_trabajador FROM usuarios WHERE usuario = ? AND contraseña = ?",
                      (usuario, contraseña))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['usuario'] = user[1]
            session['es_trabajador'] = user[2]
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos')
    
    return render_template_string(VISTA_LOGIN)

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        email = request.form.get('email')
        contraseña = request.form.get('contraseña')
        confirmar_contraseña = request.form.get('confirmar_contraseña')
        
        if contraseña != confirmar_contraseña:
            flash('Las contraseñas no coinciden')
            return render_template_string(VISTA_REGISTRO)
        
        if len(contraseña) < 6:
            flash('La contraseña debe tener al menos 6 caracteres')
            return render_template_string(VISTA_REGISTRO)
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        try:
            cursor.execute("INSERT INTO usuarios (usuario, contraseña, email, es_trabajador) VALUES (?, ?, ?, ?)",
                          (usuario, contraseña, email, 0))
            conn.commit()
            conn.close()
            
            # Guardar usuario en sesión temporal y redirigir a validación
            session['usuario_temp'] = usuario
            return redirect(url_for('validar_trabajador'))
        except sqlite3.IntegrityError:
            flash('Este usuario ya está registrado')
            return render_template_string(VISTA_REGISTRO)
    
    return render_template_string(VISTA_REGISTRO)

@app.route('/validar-trabajador', methods=['GET', 'POST'])
def validar_trabajador():
    # Verificar que el usuario está en registro
    if 'usuario_temp' not in session:
        return redirect(url_for('login'))
    
    usuario_temp = session['usuario_temp']
    
    if request.method == 'POST':
        codigo_trabajador = request.form.get('codigo_trabajador')
        
        # Verificar si el código es válido
        if codigo_trabajador in CREDENCIALES_VALIDAS:
            # Actualizar usuario como trabajador validado
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute("UPDATE usuarios SET es_trabajador = 1 WHERE usuario = ?", (usuario_temp,))
            conn.commit()
            conn.close()
            
            # Limpiar sesión temporal y establecer sesión real
            session.pop('usuario_temp', None)
            session['usuario'] = usuario_temp
            session['es_trabajador'] = 1
            
            flash('¡Identidad validada correctamente!')
            return redirect(url_for('dashboard'))
        else:
            flash('Código de trabajador inválido. Intenta nuevamente.')
    
    return render_template_string(VISTA_VALIDAR_TRABAJADOR, usuario=usuario_temp)

@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    if not session.get('es_trabajador'):
        flash('Debes validar tu identidad de trabajador primero')
        return redirect(url_for('validar_trabajador'))
    
    return render_template_string(VISTA_DASHBOARD, usuario=session['usuario'])

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente')
    return redirect(url_for('login'))

@app.route('/agregar-laptop')
def agregar_laptop():
    if 'usuario' not in session or not session.get('es_trabajador'):
        return redirect(url_for('login'))
    return "<h1>Página de agregar laptop (En desarrollo)</h1>"

@app.route('/ver-laptops')
def ver_laptops():
    if 'usuario' not in session or not session.get('es_trabajador'):
        return redirect(url_for('login'))
    return "<h1>Inventario de laptops (En desarrollo)</h1>"

@app.route('/perfil')
def perfil():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    return f"<h1>Perfil de {session['usuario']}</h1>"

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)