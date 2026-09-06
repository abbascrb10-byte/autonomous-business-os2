"""Initial schema

Revision ID: 65c9cbfe255b
Revises:
Create Date: 2026-09-06 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '65c9cbfe255b'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'demand_signals',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('source_id', sa.String(length=100), nullable=False),
        sa.Column('raw_content', sa.Text(), nullable=False),
        sa.Column('normalized_content', sa.Text(), nullable=True),
        sa.Column('dedup_hash', sa.String(length=64), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('contact_identifier', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dedup_hash')
    )
    op.create_index('ix_demand_signals_source_type', 'demand_signals', ['source_type'])
    op.create_index('ix_demand_signals_contact_identifier', 'demand_signals', ['contact_identifier'])

    op.create_table(
        'purchase_intents',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('demand_signal_id', sa.String(length=36), nullable=False),
        sa.Column('has_intent', sa.Boolean(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('intent_stage', sa.String(length=50), nullable=False),
        sa.Column('scoring_rationale', sa.Text(), nullable=False),
        sa.Column('is_qualified', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['demand_signal_id'], ['demand_signals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'product_requirements',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('purchase_intent_id', sa.String(length=36), nullable=False),
        sa.Column('product_name', sa.String(length=255), nullable=False),
        sa.Column('brand', sa.String(length=100), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('budget_max', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.Column('condition', sa.String(length=50), nullable=False),
        sa.Column('destination_country', sa.String(length=100), nullable=True),
        sa.Column('shipping_preferences', sa.String(length=255), nullable=True),
        sa.Column('specifications', sa.JSON(), nullable=True),
        sa.Column('urgency', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['purchase_intent_id'], ['purchase_intents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('purchase_intent_id')
    )

    op.create_table(
        'merchants',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('credentials_configured', sa.Boolean(), nullable=False),
        sa.Column('commission_rate_estimate', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    op.create_table(
        'offers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('purchase_intent_id', sa.String(length=36), nullable=False),
        sa.Column('merchant_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('external_product_id', sa.String(length=100), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('affiliate_url', sa.Text(), nullable=True),
        sa.Column('availability', sa.Boolean(), nullable=False),
        sa.Column('seller_name', sa.String(length=100), nullable=True),
        sa.Column('shipping_cost', sa.Float(), nullable=True),
        sa.Column('return_policy', sa.String(length=255), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False),
        sa.Column('is_test_offer', sa.Boolean(), nullable=False),
        sa.Column('product_match_score', sa.Float(), nullable=False),
        sa.Column('rank_score', sa.Float(), nullable=False),
        sa.Column('win_rationale', sa.Text(), nullable=True),
        sa.Column('freshness_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id']),
        sa.ForeignKeyConstraint(['purchase_intent_id'], ['purchase_intents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'contacts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('identifier', sa.String(length=255), nullable=False),
        sa.Column('channel', sa.String(length=50), nullable=False),
        sa.Column('permission_status', sa.String(length=50), nullable=False),
        sa.Column('permission_requested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('permission_granted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('identifier')
    )

    op.create_table(
        'outreach_messages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('contact_id', sa.String(length=36), nullable=False),
        sa.Column('purchase_intent_id', sa.String(length=36), nullable=True),
        sa.Column('offer_id', sa.String(length=36), nullable=True),
        sa.Column('message_type', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('delivery_provider', sa.String(length=50), nullable=False),
        sa.Column('delivery_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['offer_id'], ['offers.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['purchase_intent_id'], ['purchase_intents.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'clicks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tracking_token', sa.String(length=64), nullable=False),
        sa.Column('offer_id', sa.String(length=36), nullable=False),
        sa.Column('purchase_intent_id', sa.String(length=36), nullable=False),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('clicked_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['offer_id'], ['offers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['purchase_intent_id'], ['purchase_intents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tracking_token')
    )

    op.create_table(
        'conversions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('external_conversion_id', sa.String(length=100), nullable=False),
        sa.Column('click_id', sa.String(length=36), nullable=False),
        sa.Column('merchant_id', sa.String(length=36), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('converted_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['click_id'], ['clicks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_conversion_id')
    )

    op.create_table(
        'commissions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('conversion_id', sa.String(length=36), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['conversion_id'], ['conversions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('conversion_id')
    )

    op.create_table(
        'events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=36), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'agent_runs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workflow_id', sa.String(length=64), nullable=False),
        sa.Column('demand_signal_id', sa.String(length=36), nullable=True),
        sa.Column('current_node', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('state_data', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('actor', sa.String(length=100), nullable=False),
        sa.Column('policy_checked', sa.String(length=100), nullable=True),
        sa.Column('decision', sa.String(length=50), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'learning_outcomes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('purchase_intent_id', sa.String(length=36), nullable=False),
        sa.Column('offer_id', sa.String(length=36), nullable=True),
        sa.Column('merchant_id', sa.String(length=36), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('score_delta', sa.Float(), nullable=False),
        sa.Column('feedback_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['offer_id'], ['offers.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['purchase_intent_id'], ['purchase_intents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('learning_outcomes')
    op.drop_table('audit_logs')
    op.drop_table('agent_runs')
    op.drop_table('events')
    op.drop_table('commissions')
    op.drop_table('conversions')
    op.drop_table('clicks')
    op.drop_table('outreach_messages')
    op.drop_table('contacts')
    op.drop_table('offers')
    op.drop_table('merchants')
    op.drop_table('product_requirements')
    op.drop_table('purchase_intents')
    op.drop_table('demand_signals')
