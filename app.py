from app import create_app, db
from app.models.users import User, UserRole
from app.services.logging_service import LoggingService
import os

app = create_app()

@app.cli.command('init-db')
def init_db():
    """Initialize the database with tables and admin user"""
    try:
        # Create all tables
        db.create_all()
        
        # Create admin user if it doesn't exist
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                email='admin@mediadownloader.com',
                password='admin123',
                role=UserRole.ADMIN
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Admin user created: admin/admin123")
        else:
            print("Admin user already exists")
        
        print("Database initialized successfully!")
        
    except Exception as e:
        print(f"Error initializing database: {str(e)}")

@app.cli.command('create-user')
def create_user():
    """Create a new user"""
    import click
    
    username = click.prompt('Username')
    email = click.prompt('Email')
    password = click.prompt('Password', hide_input=True)
    role = click.prompt('Role', type=click.Choice(['admin', 'operator', 'viewer']))
    
    try:
        user = User(
            username=username,
            email=email,
            password=password,
            role=UserRole(role)
        )
        db.session.add(user)
        db.session.commit()
        print(f"User {username} created successfully!")
        
    except Exception as e:
        print(f"Error creating user: {str(e)}")

@app.cli.command('setup-servers')
def setup_servers():
    """Setup default servers"""
    from app.models.servers import Server, ServerProtocol
    
    try:
        # Check if servers already exist
        if Server.query.count() > 0:
            print("Servers already configured")
            return
        
        # Movies Server
        movies_server = Server(
            name='Movies Server',
            description='Servidor dedicado para filmes',
            host='192.168.1.10',
            protocol=ServerProtocol.SFTP,
            port=22,
            username='media_user',
            base_path='/mnt/',
            content_types=['movie'],
            directory_structure={
                'movie': [
                    'Acao', 'Animacao_Infantil', 'Animes', 'Cinema', 
                    'Comedia', 'Documentarios', 'Drama', 'Faroeste',
                    'Ficcao_Fantasia', 'Filmes_Legendados', 'Guerra',
                    'Lancamentos', 'Marvel', 'Romance', 'Suspense', 'Terror'
                ]
            }
        )
        movies_server.set_password('password123')
        
        # Series Server
        series_server = Server(
            name='Series Server',
            description='Servidor dedicado para séries',
            host='192.168.1.11',
            protocol=ServerProtocol.SFTP,
            port=22,
            username='media_user',
            base_path='/mnt/',
            content_types=['series'],
            directory_structure={
                'series': [
                    'Amazon', 'Animes_(Dub)', 'Animes_(Leg)', 'Apple_Tv',
                    'Desenhos_Animados', 'DiscoveryPlus', 'DisneyPlus',
                    'Drama', 'Globo_Play', 'HBOMax', 'Lionsgate', 'Looke',
                    'Natgeo', 'Netflix', 'ParamountPlus', 'Star_Plus'
                ]
            }
        )
        series_server.set_password('password123')
        
        # Novelas Server
        novelas_server = Server(
            name='Novelas Server',
            description='Servidor dedicado para novelas',
            host='192.168.1.12',
            protocol=ServerProtocol.SFTP,
            port=22,
            username='media_user',
            base_path='/mnt/',
            content_types=['novela'],
            directory_structure={
                'novela': ['Novelas']
            }
        )
        novelas_server.set_password('password123')
        
        # Add servers to database
        db.session.add(movies_server)
        db.session.add(series_server)
        db.session.add(novelas_server)
        db.session.commit()
        
        print("Default servers configured successfully!")
        print("Movies Server: 192.168.1.10")
        print("Series Server: 192.168.1.11")
        print("Novelas Server: 192.168.1.12")
        print("Default password: password123")
        
    except Exception as e:
        print(f"Error setting up servers: {str(e)}")

if __name__ == '__main__':
    app.run(
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=app.config['FLASK_DEBUG']
    )


