from flask import Blueprint, jsonify, request, session, current_app
from app.extensions import db, jwt, bcrypt
from werkzeug.utils import secure_filename
import os
from app.models.user import SystemUser, UserRole
from uuid import uuid4
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, unset_jwt_cookies, set_access_cookies, decode_token
from app.exceptions import ValidationError, UnauthorizedError, ForbiddenError, AppError, BadRequestError, NotFoundError, ConflictError
from app.utils.helper import issue_tokens_for_user
from datetime import datetime, timezone, timedelta, date
import re
from functools import wraps
from app.utils.decorators import requires_coordinator_or_admin

user_bp = Blueprint("user", __name__, url_prefix='/user')


# Configuración
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../../uploads/avatars')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Crear carpeta si no existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@user_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    
    # Validación de campos requeridos
    if not email or not password:
        raise UnauthorizedError("Email y contraseña son requeridos")
    
    # Verificar si el usuario existe
    user = SystemUser.query.filter_by(email=email).first()
    if not user:
        raise UnauthorizedError("Credenciales inválidas")
    
    # Verificar contraseña
    if not bcrypt.check_password_hash(user.password, password):
        raise UnauthorizedError("Credenciales inválidas")
    
    # Verificar si el usuario está activo o es su primer login
    if not user.is_active:
        if user.last_login is None:
            # Primer login - activar automáticamente
            user.is_active = True
        else:
            raise UnauthorizedError("Usuario inactivo. Contacte al administrador.")
    
    # SOLO si pasó todas las verificaciones: Login exitoso
    user.last_login = datetime.now(timezone.utc)
    db.session.commit()
    
    # Generar token JWT
    access_token = issue_tokens_for_user(user)
    
    response = jsonify({
        "msg": "Login successful",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "last_name": user.last_name,
            "rol": user.rol.value,
            "css_id": user.css_id
        },
        "role": user.rol.value
    })
    
    set_access_cookies(response, access_token)
    return response


@user_bp.route("/me", methods=["GET"])
@jwt_required()
def get_current_user():
    current_user_id = get_jwt_identity()
    user = SystemUser.query.get(current_user_id)
    
    if not user or not user.is_active:
        raise UnauthorizedError("Usuario no válido")
    
    return jsonify({
        "user": {
            "id": user.id,
            "name": user.name,
            "last_name": user.last_name,
            "email": user.email,
            "rol": user.rol.value,
            "css_id": user.css_id,
            "avatar_url": user.avatar_url,
            "avatar_type": user.avatar_type,
            "avatar_style": user.avatar_style,
            "avatar_color": user.avatar_color,
            "avatar_seed": user.avatar_seed
        },
        "role": user.rol.value 
    })


# =================================================================
#   RUTAS PARA OBTENER PERFIL DEL USUARIO O INFORMACION DEL USUARIO
# ==================================================================

@user_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_current_user_profile():
    """Obtener perfil completo del usuario actual.
    Returns: 
        200: Perfil completo del usuario
        404: Usuario no encontrado
    No requiere confirmación - solo lectura"""
    
    current_user_id = get_jwt_identity()
    user = SystemUser.query.get(current_user_id)
    
    if not user or not user.is_active:
        raise UnauthorizedError("Usuario no válido")
    
    return jsonify({
        "success": True,
        "user": {
            "id": user.id,
            "name": user.name,
            "last_name": user.last_name,
            "email": user.email,
            "dni": user.dni,
            "phone": user.phone,
            "birth_date": user.birth_date.isoformat() if user.birth_date else None,
            "age": user.age,
            "address": user.address,
            "observations": user.observations,
            "css_id": user.css_id,
            "rol": user.rol.value,
            "is_active": user.is_active,
            # Campos del avatar
            "avatar_url": user.avatar_url,
            "avatar_type": user.avatar_type,
            "avatar_style": user.avatar_style,
            "avatar_color": user.avatar_color,
            "avatar_seed": user.avatar_seed,
            # Timestamps
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None
        }
    }), 200


# =================================================================
#           RUTA PARA ACTUALIZAR EL PERFIL DEL USUARIO
# ==================================================================

@user_bp.route("/profile", methods=["PUT"])
@jwt_required()
def update_current_user_profile():
    """Actualizar perfil del usuario actual. Body:
        - name: string (opcional)
        - last_name: string (opcional)
        - phone: string (opcional)
        - address: string (opcional)
    Returns:
        200: Perfil actualizado exitosamente
        400: Datos inválidos
        404: Usuario no encontrado
    """
    try:
        current_user_id = get_jwt_identity()
        user = SystemUser.query.get(current_user_id)
        
        if not user or not user.is_active:
            raise UnauthorizedError("Usuario no válido")
        
        # Obtener datos del request
        data = request.get_json(silent=True) or {}
        if not data:
            raise BadRequestError("No se proporcionaron datos para actualizar")

        # Array para trackear cambios
        changes_made = []
        
        # ========== CAMPOS PERSONALES (todos opcionales) ==========
        
        # Actualizar nombre
        if 'name' in data:
            new_name = data['name'].strip() if data['name'] else ''
            if new_name and user.name != new_name:
                user.name = new_name
                changes_made.append("nombre")
        
        # Actualizar apellidos
        if 'last_name' in data:
            new_last_name = data['last_name'].strip() if data['last_name'] else ''
            if new_last_name and user.last_name != new_last_name:
                user.last_name = new_last_name
                changes_made.append("apellidos")
        
        # Actualizar teléfono
        if 'phone' in data:
            new_phone = data['phone'].strip() if data['phone'] else None
            if new_phone:
                # Validar formato básico de teléfono
                if len(new_phone) < 8:
                    raise BadRequestError("El número de teléfono es demasiado corto")
                
                if user.phone != new_phone:
                    user.phone = new_phone
                    changes_made.append("teléfono")
        
        # Actualizar dirección
        if 'address' in data:
            new_address = data['address'].strip() if data['address'] else None
            if user.address != new_address:
                user.address = new_address
                changes_made.append("dirección")
        
        # ========== FINALIZACIÓN ==========
        
        # Si no hubo cambios, informarlo
        if not changes_made:
            return jsonify({
                "success": True,
                "message": "No se realizaron cambios",
                "user": {
                    "name": user.name,
                    "last_name": user.last_name,
                    "phone": user.phone,
                    "address": user.address,
                    "avatar_url": user.avatar_url,
                    "avatar_type": user.avatar_type,
                    "avatar_style": user.avatar_style,
                    "avatar_color": user.avatar_color,
                    "avatar_seed": user.avatar_seed
                }
            }), 200
        
        # Actualizar timestamp y guardar
        user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Perfil actualizado exitosamente. Cambios realizados: {', '.join(changes_made)}",
            "user": {
                "name": user.name,
                "last_name": user.last_name,
                "phone": user.phone,
                "address": user.address,
                "avatar_url": user.avatar_url,
                "avatar_type": user.avatar_type,
                "avatar_style": user.avatar_style,
                "avatar_color": user.avatar_color,
                "avatar_seed": user.avatar_seed,
                "updated_at": user.updated_at.isoformat()
            }
        }), 200
        
    except (BadRequestError, ConflictError, UnauthorizedError) as e:
        db.session.rollback()
        raise e
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ========================================
# ENDPOINT: Cambiar Contraseña
# ========================================

@user_bp.route('/profile/password', methods=['PUT'])
@jwt_required()
def update_password():
    """
    Cambiar contraseña del usuario
    """
    try:
        current_user_id = get_jwt_identity()
        user = SystemUser.query.get(current_user_id)
        
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404
        
        data = request.get_json()
        
        # Validar campos requeridos
        if not all(k in data for k in ('current_password', 'new_password', 'confirm_password')):
            return jsonify({"error": "Faltan campos requeridos"}), 400
        
        # ✅ Verificar contraseña actual
        if not bcrypt.check_password_hash(user.password, data['current_password']):
            return jsonify({"error": "Contraseña actual incorrecta"}), 401
        
        # Verificar que las nuevas contraseñas coincidan
        if data['new_password'] != data['confirm_password']:
            return jsonify({"error": "Las nuevas contraseñas no coinciden"}), 400
        
        # Validar longitud mínima
        if len(data['new_password']) < 8:
            return jsonify({"error": "La contraseña debe tener al menos 8 caracteres"}), 400
        
        # ✅ Actualizar contraseña correctamente
        user.password = bcrypt.generate_password_hash(data['new_password']).decode('utf-8')
        user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Contraseña actualizada exitosamente"
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ========================================
# ENDPOINT: Actualizar Avatar
# ========================================

@user_bp.route('/profile/avatar', methods=['PUT'])
@jwt_required()
def update_avatar():
    """
    Actualizar avatar del usuario.
    Sistema mejorado que guarda la URL y metadata para regenerar.
    
    Body esperado:
    {
        "avatar_type": "dicebear" | "initials",
        "avatar_url": "https://...",
        "avatar_style": "adventurer" (solo para dicebear),
        "avatar_color": "E9531A" (solo para initials),
        "avatar_seed": "usuario123" (opcional)
    }
    """
    try:
        current_user_id = get_jwt_identity()
        user = SystemUser.query.get(current_user_id)
        
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404
        
        data = request.get_json()
        
        # Validar tipo de avatar
        avatar_type = data.get('avatar_type')
        if avatar_type not in ['dicebear', 'initials']:
            return jsonify({"error": "Tipo de avatar inválido"}), 400
        
        # Validar URL del avatar
        avatar_url = data.get('avatar_url')
        if not avatar_url:
            return jsonify({"error": "URL del avatar es requerida"}), 400
        
        # Actualizar datos del avatar
        user.avatar_url = avatar_url
        user.avatar_type = avatar_type
        
        # Guardar metadata según el tipo
        if avatar_type == 'dicebear':
            user.avatar_style = data.get('avatar_style', 'adventurer')
            user.avatar_seed = data.get('avatar_seed', '')
            user.avatar_color = None  # No aplica para dicebear
        
        elif avatar_type == 'initials':
            user.avatar_color = data.get('avatar_color', 'E9531A')
            user.avatar_style = None  # No aplica para initials
            user.avatar_seed = None
        
        user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Avatar actualizado exitosamente",
            "avatar": {
                "avatar_url": user.avatar_url,
                "avatar_type": user.avatar_type,
                "avatar_style": user.avatar_style,
                "avatar_color": user.avatar_color,
                "avatar_seed": user.avatar_seed
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ========================================
# ENDPOINT: Eliminar Avatar (volver al default)
# ========================================

@user_bp.route('/profile/avatar', methods=['DELETE'])
@jwt_required()
def delete_avatar():
    """
    Eliminar avatar personalizado y volver al avatar por defecto
    """
    try:
        current_user_id = get_jwt_identity()
        user = SystemUser.query.get(current_user_id)
        
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404
        
        # Limpiar todos los datos del avatar
        user.avatar_url = None
        user.avatar_type = None
        user.avatar_style = None
        user.avatar_color = None
        user.avatar_seed = None
        
        user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Avatar eliminado exitosamente"
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    

@user_bp.route('/profile/avatar/upload', methods=['POST'])
@jwt_required()
def upload_avatar():
    """
    Subir imagen de avatar
    """
    try:
        current_user_id = get_jwt_identity()
        user = SystemUser.query.get(current_user_id)
        
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404
        
        # Verificar que hay un archivo
        if 'avatar' not in request.files:
            return jsonify({"error": "No se envió ningún archivo"}), 400
        
        file = request.files['avatar']
        
        if file.filename == '':
            return jsonify({"error": "Archivo vacío"}), 400
        
        # Validar tipo de archivo
        if not allowed_file(file.filename):
            return jsonify({"error": "Tipo de archivo no permitido"}), 400
        
        # Validar tamaño
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({"error": "El archivo es demasiado grande (máx. 5MB)"}), 400
        
        # Generar nombre único
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid4()}.{file_extension}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        # Eliminar avatar anterior si existe
        if user.avatar_url and user.avatar_type == 'upload':
            try:
                # Extraer solo el nombre del archivo
                old_filename = user.avatar_url.split('/')[-1]
                old_path = os.path.join(UPLOAD_FOLDER, old_filename)
                if os.path.exists(old_path):
                    os.remove(old_path)
            except:
                pass
        
        # Guardar archivo
        file.save(file_path)
        
        # ✅ Generar URL COMPLETA
        from flask import request as flask_request
        avatar_url = f"{flask_request.host_url}uploads/avatars/{unique_filename}"
        
        # Actualizar usuario
        user.avatar_url = avatar_url
        user.avatar_type = 'upload'
        user.avatar_style = None
        user.avatar_color = None
        user.avatar_seed = None
        user.updated_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Avatar subido exitosamente",
            "avatar": {
                "avatar_url": avatar_url,
                "avatar_type": "upload",
                "avatar_style": None,
                "avatar_color": None,
                "avatar_seed": None
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    

@user_bp.route('/professionals', methods=['GET'])
@requires_coordinator_or_admin
def get_professionals():
    """
    Obtener lista de todos los profesionales activos
    Para: Selects de asignación en talleres y sesiones
    """
    try:
        professionals = SystemUser.query.filter(
            SystemUser.rol == UserRole.PROFESSIONAL,
            SystemUser.is_active == True
        ).order_by(SystemUser.name).all()
        
        return jsonify({
            "professionals": [
                {
                    "id": prof.id,
                    "name": prof.name,
                    "last_name": prof.last_name,
                    "email": prof.email,
                    "css_id": prof.css_id,
                    "css_name": prof.css.name if prof.css else None
                }
                for prof in professionals
            ],
            "total": len(professionals)
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500