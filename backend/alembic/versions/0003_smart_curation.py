"""Member labels and a stored comparative best-shot score for smart curation."""
import json

import sqlalchemy as sa
from alembic import op

revision='0003'
down_revision='0002'
branch_labels=None
depends_on=None


def _score(quality, faces):
    from app.image_service import best_shot_score
    return best_shot_score(quality, faces)


def _decode(value, fallback):
    if value is None: return fallback
    if isinstance(value, (dict, list)): return value
    try: return json.loads(value)
    except (TypeError, ValueError): return fallback


def upgrade():
    op.create_table('labels',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('album_id', sa.String(36), sa.ForeignKey('albums.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(40), nullable=False),
        sa.Column('color', sa.String(7), nullable=False, server_default='#2563eb'),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('album_id','name', name='uq_label_album_name'))
    op.create_index('ix_labels_album_id', 'labels', ['album_id'])
    op.create_table('photo_labels',
        sa.Column('photo_id', sa.String(36), sa.ForeignKey('photos.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('label_id', sa.String(36), sa.ForeignKey('labels.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.add_column('photos', sa.Column('best_shot_score', sa.Float(), nullable=True))
    # Backfill from stored analysis output so recommendation ordering works before any reanalysis.
    bind = op.get_bind()
    rows = bind.execute(sa.text('SELECT id, quality, faces FROM photos WHERE analysis_status = :status'),
                        {'status': 'completed'}).fetchall()
    for photo_id, quality, faces in rows:
        score = _score(_decode(quality, {}), _decode(faces, []))
        if score is None: continue
        bind.execute(sa.text('UPDATE photos SET best_shot_score = :score WHERE id = :id'),
                     {'score': score, 'id': photo_id})


def downgrade():
    op.drop_column('photos', 'best_shot_score')
    op.drop_table('photo_labels')
    op.drop_index('ix_labels_album_id', table_name='labels')
    op.drop_table('labels')
