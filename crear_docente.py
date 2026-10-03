"""
Crea (o restablece) la cuenta docente. Se ejecuta UNA vez:

    py crear_docente.py

Para la base publicada, lo más simple es definir [docente] en los secretos de Streamlit
(ver LEEME_APP.md). Sin ella, crea la cuenta en la base local its_local.db.
"""
import getpass

from its_web import db, seguridad


def main():
    print(f'Base de datos: {db._url().split("@")[-1]}')
    usuario = input('Usuario docente: ').strip()
    error = seguridad.validar_usuario(usuario)
    if error:
        print(error)
        return
    clave = getpass.getpass('Contraseña (mínimo 8 caracteres, no se muestra): ')
    error = seguridad.validar_clave(clave)
    if error or clave != getpass.getpass('Repite la contraseña: '):
        print(error or 'Las contraseñas no coinciden.')
        return
    nombre = input('Nombre a mostrar: ').strip()
    existente = db.buscar_usuario(usuario)
    if existente:
        db.actualizar_usuario(existente['id'], hash=seguridad.hashear(clave), rol='docente', nombre=nombre)
        print('Cuenta existente actualizada como docente.')
    else:
        db.crear_usuario(usuario, seguridad.hashear(clave), nombre, rol='docente')
        print('Cuenta docente creada.')


if __name__ == '__main__':
    main()
