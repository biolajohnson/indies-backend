"""
Seed script — populates the database with sample filmmakers, campaigns, and donations.
Run with: python seed.py
"""
from datetime import datetime, timezone, timedelta
from app import create_app
from extensions import db
from models import Filmmaker, Campaign, Donation, CampaignUpdate


def seed():
    app = create_app("development")

    with app.app_context():
        # Wipe existing data
        db.drop_all()
        db.create_all()

        print("Seeding filmmakers...")

        ava = Filmmaker(
            name="Ava Richardson",
            email="ava@example.com",
            bio=(
                "Ava Richardson is an award-winning filmmaker known for her visually "
                "poetic storytelling and strong female leads. With a background in marine "
                "biology and visual arts, she crafts narratives that explore the "
                "intersection of nature, identity, and belief."
            ),
            nationality="Canadian",
            website="https://www.avarichardsonfilms.com",
            social_links={
                "instagram": "@ava.richardson",
                "twitter": "@ava_directs",
                "imdb": "https://www.imdb.com/name/nm1234567/",
            },
        )
        ava.set_password("password123")

        marcus = Filmmaker(
            name="Marcus Osei",
            email="marcus@example.com",
            bio=(
                "Marcus Osei is a Ghanaian-British filmmaker whose work explores "
                "diaspora identity, memory, and belonging. His debut short 'Harmattan' "
                "screened at over 30 festivals worldwide."
            ),
            nationality="British-Ghanaian",
            website="https://www.marcusosei.com",
            social_links={
                "instagram": "@marcusosei.film",
                "twitter": "@marcusosei",
            },
        )
        marcus.set_password("password123")

        db.session.add_all([ava, marcus])
        db.session.flush()  # Get IDs before committing

        print("Seeding campaigns...")

        campaign1 = Campaign(
            filmmaker_id=ava.id,
            title="Beneath the Horizon",
            short_description=(
                "A young marine scientist uncovers ancient signals beneath the ocean "
                "floor — and the truth that could upend everything she believes."
            ),
            description=(
                "In a remote coastal village, Dr. Lena Park makes a discovery that "
                "shouldn't exist: a pattern of electromagnetic pulses originating from "
                "the deep ocean floor, repeating on a 7-year cycle dating back millennia.\n\n"
                "As Lena digs deeper, she finds herself drawn into a conflict between "
                "scientific consensus and something far older. The film explores what "
                "happens when evidence points somewhere the world isn't ready to look.\n\n"
                "This campaign will fund principal photography, a six-week shoot on "
                "location on Vancouver Island, and post-production through a "
                "festival-ready cut."
            ),
            goal_amount=45000.00,
            current_amount=18750.00,
            genre="Science Fiction, Mystery",
            tags=["sci-fi", "mystery", "female-lead", "ocean", "indie film"],
            status=Campaign.STATUS_ACTIVE,
            deadline=datetime.now(timezone.utc) + timedelta(days=42),
        )

        campaign2 = Campaign(
            filmmaker_id=marcus.id,
            title="The Weight of Letters",
            short_description=(
                "A retired Ghanaian postman walks 200 miles across Accra to hand-deliver "
                "letters that were lost in a flood 30 years ago."
            ),
            description=(
                "When Kofi Mensah retired after 40 years as a postman, he thought his "
                "work was done. Then a flood in the Accra central sorting office revealed "
                "a cache of letters from the early 1990s — never delivered.\n\n"
                "Kofi decides to walk every route himself, letter by letter, finding the "
                "recipients or their families. What follows is a film about how words "
                "travel across time, and what it means to finally be heard.\n\n"
                "Budget covers a 4-week Ghana shoot, two local crew members, "
                "and a documentary-style post-production workflow."
            ),
            goal_amount=28000.00,
            current_amount=6200.00,
            genre="Drama, Documentary",
            tags=["drama", "ghana", "diaspora", "human interest", "walking film"],
            status=Campaign.STATUS_ACTIVE,
            deadline=datetime.now(timezone.utc) + timedelta(days=60),
        )

        campaign3 = Campaign(
            filmmaker_id=ava.id,
            title="Saltwater Dreaming — Director's Cut",
            short_description=(
                "The Sundance-awarded short film, restored and extended with 22 minutes "
                "of never-before-seen footage."
            ),
            description=(
                "Saltwater Dreaming won the Sundance Special Jury Prize in 2021. "
                "This campaign funds a full director's cut restoration — color grading "
                "with the original DP, a new score recorded with a live orchestra, and "
                "22 minutes of additional scenes that were cut for time in the original "
                "festival version.\n\n"
                "Backers get early access to the restored film and a behind-the-scenes "
                "documentary about the restoration process."
            ),
            goal_amount=15000.00,
            current_amount=15000.00,
            genre="Drama",
            tags=["drama", "restoration", "short film", "ocean", "female-lead"],
            status=Campaign.STATUS_FUNDED,
            deadline=datetime.now(timezone.utc) - timedelta(days=5),
        )

        db.session.add_all([campaign1, campaign2, campaign3])
        db.session.flush()

        print("Seeding donations...")

        donations = [
            Donation(campaign_id=campaign1.id, donor_email="supporter1@example.com",
                     donor_name="Sarah K.", amount=250.00,
                     message="Ava's work is incredible. Can't wait to see this one.", is_anonymous=False),
            Donation(campaign_id=campaign1.id, donor_email="anon@example.com",
                     donor_name=None, amount=100.00, is_anonymous=True),
            Donation(campaign_id=campaign1.id, donor_email="james@example.com",
                     donor_name="James Okafor", amount=500.00,
                     message="The ocean needs more stories like this.", is_anonymous=False),
            Donation(campaign_id=campaign2.id, donor_email="priya@example.com",
                     donor_name="Priya M.", amount=75.00,
                     message="This story moved me. Wishing Marcus all the best.", is_anonymous=False),
            Donation(campaign_id=campaign2.id, donor_email="will@example.com",
                     donor_name="Will T.", amount=200.00, is_anonymous=False),
            Donation(campaign_id=campaign3.id, donor_email="nina@example.com",
                     donor_name="Nina Bergström", amount=500.00,
                     message="Saltwater Dreaming changed how I see film.", is_anonymous=False),
        ]
        db.session.add_all(donations)
        db.session.flush()

        # Update campaign totals (seed is direct — bypasses the route logic)
        campaign1.current_amount = sum(d.amount for d in donations if d.campaign_id == campaign1.id)
        campaign2.current_amount = sum(d.amount for d in donations if d.campaign_id == campaign2.id)

        print("Seeding campaign updates...")

        updates = [
            CampaignUpdate(
                campaign_id=campaign1.id,
                title="Location scouting begins next week!",
                body=(
                    "We're heading to Vancouver Island next week to scout locations. "
                    "The coastline near Tofino is everything we imagined for Lena's "
                    "research station. Stay tuned for photos."
                ),
            ),
            CampaignUpdate(
                campaign_id=campaign1.id,
                title="We hit 40% funding — thank you!",
                body=(
                    "We're overwhelmed by your support. 40% funded in the first two weeks "
                    "is beyond what we hoped for. Share the campaign with anyone who loves "
                    "thoughtful science fiction — every donation brings us closer to camera."
                ),
            ),
            CampaignUpdate(
                campaign_id=campaign3.id,
                title="Fully funded! Recording starts Monday.",
                body=(
                    "We did it. The Vancouver Symphony Orchestra has confirmed our session "
                    "dates. Recording starts Monday. This would not have been possible "
                    "without every single one of you."
                ),
            ),
        ]
        db.session.add_all(updates)
        db.session.commit()

        print("\n✅ Database seeded successfully!")
        print(f"   Filmmakers: 2 (login with ava@example.com / password123)")
        print(f"   Campaigns:  3 (2 active, 1 funded)")
        print(f"   Donations:  {len(donations)}")
        print(f"   Updates:    {len(updates)}")


if __name__ == "__main__":
    seed()
