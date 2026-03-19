import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'супер-секретный-ключ-для-сессий'  # Обязательно для Flask-Login

# Настройка Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Имя функции для роута входа
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице'

# Модель User
class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash
    
    @staticmethod
    def get(user_id):
        conn = sqlite3.connect('blog.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, password_hash FROM users WHERE id = ?', (user_id,))
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data:
            return User(user_data[0], user_data[1], user_data[2])
        return None
    
    @staticmethod
    def find_by_username(username):
        conn = sqlite3.connect('blog.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, password_hash FROM users WHERE username = ?', (username,))
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data:
            return User(user_data[0], user_data[1], user_data[2])
        return None

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# Инициализация БД
def init_db():
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    
    # Таблица постов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()
    print("База данных инициализирована")

# Роут для создания первого администратора (УДАЛИТЬ ПОСЛЕ ИСПОЛЬЗОВАНИЯ!)
@app.route('/setup-admin')
def setup_admin():
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    
    # Проверим, есть ли уже пользователи
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    
    if count == 0:
        # Создаем администратора
        username = 'admin'
        password = 'admin123'  # Поменяй на свой пароль!
        password_hash = generate_password_hash(password)
        
        cursor.execute(
            'INSERT INTO users (username, password_hash) VALUES (?, ?)',
            (username, password_hash)
        )
        conn.commit()
        conn.close()
        return 'Администратор создан! Логин: admin, Пароль: admin123'
    else:
        conn.close()
        return 'Администратор уже существует'

# Публичные роуты
@app.route('/')
def index():
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, content, created_at FROM posts ORDER BY created_at DESC')
    posts = cursor.fetchall()
    conn.close()
    
    return render_template('index.html', posts=posts)

@app.route('/post/<int:post_id>')
def show_post(post_id):
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, content, created_at FROM posts WHERE id = ?', (post_id,))
    post = cursor.fetchone()
    conn.close()
    
    if post:
        return render_template('post.html', post=post)
    else:
        return render_template('404.html'), 404

# Роуты аутентификации
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.find_by_username(username)
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Вы успешно вошли в систему!')
            return redirect(url_for('admin'))
        else:
            flash('Неверное имя пользователя или пароль')
            return render_template('login.html')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы')
    return redirect(url_for('index'))

# Админ-роуты (защищенные)
@app.route('/admin')
@login_required
def admin():
    # Получаем все посты из БД для отображения в админке
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, created_at FROM posts ORDER BY created_at DESC')
    posts = cursor.fetchall()
    conn.close()
    
    return render_template('admin/dashboard.html', posts=posts)

@app.route('/admin/post/new', methods=['GET', 'POST'])
@login_required
def new_post():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        
        conn = sqlite3.connect('blog.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO posts (title, content) VALUES (?, ?)',
            (title, content)
        )
        conn.commit()
        conn.close()
        
        flash('Пост успешно создан!')
        return redirect(url_for('admin'))
    
    return render_template('admin/post_form.html')

@app.route('/admin/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        
        cursor.execute(
            'UPDATE posts SET title = ?, content = ? WHERE id = ?',
            (title, content, post_id)
        )
        conn.commit()
        conn.close()
        
        flash('Пост успешно обновлен!')
        return redirect(url_for('admin'))
    
    # GET запрос - показываем форму с данными поста
    cursor.execute('SELECT title, content FROM posts WHERE id = ?', (post_id,))
    post = cursor.fetchone()
    conn.close()
    
    if post:
        return render_template('admin/post_form.html', post=post)
    else:
        flash('Пост не найден')
        return redirect(url_for('admin'))

@app.route('/admin/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM posts WHERE id = ?', (post_id,))
    conn.commit()
    conn.close()
    
    flash('Пост удален')
    return redirect(url_for('admin'))

# Обработчик ошибки 404
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    init_db()  # Создаем таблицы при запуске
    app.run(debug=True)