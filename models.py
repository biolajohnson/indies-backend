from datetime import datetime, timezone
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash


class Filmmaker(db.Model):
    __tablename__ = "filmmakers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    avatar_url = db.Column(db.String(500), nullable=True)
    nationality = db.Column(db.String(100), nullable=True)
    website = db.Column(db.String(500), nullable=True)
    # JSON blob: { "instagram": "@handle", "twitter": "@handle", "imdb": "url" }
    social_links = db.Column(db.JSON, nullable=True, default=dict)
    stripe_account_id = db.Column(db.String(255), nullable=True)
    stripe_onboarded = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    campaigns = db.relationship("Campaign", back_populates="filmmaker", lazy="select")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self, include_private=False):
        data = {
            "id": self.id,
            "name": self.name,
            "bio": self.bio,
            "avatar_url": self.avatar_url,
            "nationality": self.nationality,
            "website": self.website,
            "social_links": self.social_links or {},
            "stripe_onboarded": self.stripe_onboarded,
            "created_at": self.created_at.isoformat(),
            "campaigns": [c.to_dict() for c in self.campaigns],
        }
        if include_private:
            data["email"] = self.email
            data["stripe_account_id"] = self.stripe_account_id
        return data


class Campaign(db.Model):
    __tablename__ = "campaigns"

    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_FUNDED = "funded"
    STATUS_CLOSED = "closed"
    VALID_STATUSES = [STATUS_DRAFT, STATUS_ACTIVE, STATUS_FUNDED, STATUS_CLOSED]

    id = db.Column(db.Integer, primary_key=True)
    filmmaker_id = db.Column(db.Integer, db.ForeignKey("filmmakers.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    short_description = db.Column(db.String(500), nullable=True)
    goal_amount = db.Column(db.Numeric(10, 2), nullable=False)
    current_amount = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    video_url = db.Column(db.String(500), nullable=True)
    thumbnail_url = db.Column(db.String(500), nullable=True)
    genre = db.Column(db.String(100), nullable=True)
    # JSON array of tag strings: ["sci-fi", "mystery", "female-lead"]
    tags = db.Column(db.JSON, nullable=True, default=list)
    status = db.Column(db.String(20), default=STATUS_DRAFT, nullable=False)
    deadline = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    filmmaker = db.relationship("Filmmaker", back_populates="campaigns")
    donations = db.relationship("Donation", back_populates="campaign", lazy="select")
    updates = db.relationship(
        "CampaignUpdate", back_populates="campaign", lazy="select", order_by="CampaignUpdate.created_at.desc()"
    )

    @property
    def percent_funded(self):
        if not self.goal_amount or self.goal_amount == 0:
            return 0
        return round((float(self.current_amount) / float(self.goal_amount)) * 100, 1)

    @property
    def donor_count(self):
        return len(self.donations)

    def to_dict(self, include_donations=False, include_updates=False):
        data = {
            "id": self.id,
            "filmmaker_id": self.filmmaker_id,
            "filmmaker_name": self.filmmaker.name if self.filmmaker else None,
            "filmmaker_avatar": self.filmmaker.avatar_url if self.filmmaker else None,
            "title": self.title,
            "description": self.description,
            "short_description": self.short_description,
            "goal_amount": float(self.goal_amount),
            "current_amount": float(self.current_amount),
            "percent_funded": self.percent_funded,
            "donor_count": self.donor_count,
            "video_url": self.video_url,
            "thumbnail_url": self.thumbnail_url,
            "genre": self.genre,
            "tags": self.tags or [],
            "status": self.status,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if include_donations:
            data["donations"] = [d.to_dict() for d in self.donations]
        if include_updates:
            data["updates"] = [u.to_dict() for u in self.updates]
        return data


class Donation(db.Model):
    __tablename__ = "donations"

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaigns.id"), nullable=False)
    # nullable: we allow anonymous donations with just an email
    filmmaker_id = db.Column(db.Integer, db.ForeignKey("filmmakers.id"), nullable=True)
    donor_name = db.Column(db.String(120), nullable=True)
    donor_email = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    message = db.Column(db.Text, nullable=True)
    stripe_payment_intent_id = db.Column(db.String(255), nullable=True, unique=True)
    # Future: tier_id FK for reward tiers (extensibility hook)
    tier_id = db.Column(db.Integer, nullable=True)
    is_anonymous = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    campaign = db.relationship("Campaign", back_populates="donations")

    def to_dict(self, include_private=False):
        data = {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "donor_name": None if self.is_anonymous else self.donor_name,
            "amount": float(self.amount),
            "message": self.message,
            "is_anonymous": self.is_anonymous,
            "created_at": self.created_at.isoformat(),
        }
        if include_private:
            data["donor_email"] = self.donor_email
            data["stripe_payment_intent_id"] = self.stripe_payment_intent_id
        return data


class CampaignUpdate(db.Model):
    __tablename__ = "campaign_updates"

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaigns.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    campaign = db.relationship("Campaign", back_populates="updates")

    def to_dict(self):
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "title": self.title,
            "body": self.body,
            "created_at": self.created_at.isoformat(),
        }
