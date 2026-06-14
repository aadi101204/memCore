"""
Alembic migration: Add authentication tables.

Revision ID: 002
Revises: 001
Create Date: 2026-02-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision = '002'
down_revision = '4cfd68e5f08e'
branch_labels = None
depends_on = None


def upgrade():
    """Add authentication tables."""
    
    # Users table
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('username', sa.String(100), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('org_id', UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    )
    
    # Indexes for users
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_username', 'users', ['username'])
    op.create_index('ix_users_org_id', 'users', ['org_id'])
    
    # API Keys table
    op.create_table(
        'api_keys',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('key_hash', sa.String(255), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('org_id', UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', UUID(as_uuid=True), nullable=True),
        sa.Column('team_id', UUID(as_uuid=True), nullable=True),
        sa.Column('scopes', sa.Text(), nullable=False, server_default='agent'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), nullable=True),
    )
    
    # Indexes for api_keys
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'])
    op.create_index('ix_api_keys_org_id', 'api_keys', ['org_id'])
    op.create_index('ix_api_keys_agent_id', 'api_keys', ['agent_id'])
    op.create_index('ix_api_keys_team_id', 'api_keys', ['team_id'])
    
    # Permissions table
    op.create_table(
        'permissions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('resource', sa.String(100), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=True),
        sa.Column('api_key_id', UUID(as_uuid=True), nullable=True),
        sa.Column('org_id', UUID(as_uuid=True), nullable=True),
        sa.Column('agent_id', UUID(as_uuid=True), nullable=True),
        sa.Column('team_id', UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), nullable=True),
    )
    
    # Indexes for permissions
    op.create_index('ix_permissions_resource', 'permissions', ['resource'])
    op.create_index('ix_permissions_action', 'permissions', ['action'])
    op.create_index('ix_permissions_user_id', 'permissions', ['user_id'])
    op.create_index('ix_permissions_api_key_id', 'permissions', ['api_key_id'])
    
    # Token blacklist table
    op.create_table(
        'token_blacklist',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('token_jti', sa.String(255), unique=True, nullable=False),
        sa.Column('token_type', sa.String(50), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('blacklisted_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # Indexes for token_blacklist
    op.create_index('ix_token_blacklist_token_jti', 'token_blacklist', ['token_jti'])
    op.create_index('ix_token_blacklist_user_id', 'token_blacklist', ['user_id'])
    op.create_index('ix_token_blacklist_expires_at', 'token_blacklist', ['expires_at'])


def downgrade():
    """Remove authentication tables."""
    op.drop_table('token_blacklist')
    op.drop_table('permissions')
    op.drop_table('api_keys')
    op.drop_table('users')
