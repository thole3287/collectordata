from flask import render_template

def index():
    """Trang chủ admin"""
    return render_template('index.html')
