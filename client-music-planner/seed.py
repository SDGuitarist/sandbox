"""Seed script: creates demo musician, 30 songs, 2 events, playlist items, and song requests."""

import secrets
from werkzeug.security import generate_password_hash
from app import create_app
from app.db import get_db
from app.models import create_user, create_song, create_event, add_playlist_item, add_song_request

app = create_app()

SONGS = [
    # Rock (5)
    {"title": "Highway Star", "artist": "Deep Purple", "genre": "rock", "musical_key": "G", "tempo": 170, "energy": 5, "duration_seconds": 370, "notes": "Classic opener"},
    {"title": "Black Dog", "artist": "Led Zeppelin", "genre": "rock", "musical_key": "A", "tempo": 168, "energy": 5, "duration_seconds": 295, "notes": ""},
    {"title": "Sultans of Swing", "artist": "Dire Straits", "genre": "rock", "musical_key": "Dm", "tempo": 148, "energy": 4, "duration_seconds": 348, "notes": "Fingerpicking intro"},
    {"title": "Roxanne", "artist": "The Police", "genre": "rock", "musical_key": "Em", "tempo": 132, "energy": 4, "duration_seconds": 195, "notes": ""},
    {"title": "Under the Bridge", "artist": "Red Hot Chili Peppers", "genre": "rock", "musical_key": "E", "tempo": 84, "energy": 3, "duration_seconds": 264, "notes": "Slow build"},
    # Pop (5)
    {"title": "Uptown Funk", "artist": "Bruno Mars", "genre": "pop", "musical_key": "Dm", "tempo": 115, "energy": 5, "duration_seconds": 270, "notes": "Crowd favorite"},
    {"title": "Happy", "artist": "Pharrell Williams", "genre": "pop", "musical_key": "F", "tempo": 160, "energy": 5, "duration_seconds": 233, "notes": ""},
    {"title": "Shape of You", "artist": "Ed Sheeran", "genre": "pop", "musical_key": "C#m", "tempo": 96, "energy": 4, "duration_seconds": 234, "notes": ""},
    {"title": "Just the Way You Are", "artist": "Bruno Mars", "genre": "pop", "musical_key": "F", "tempo": 109, "energy": 3, "duration_seconds": 221, "notes": "First dance option"},
    {"title": "Thinking Out Loud", "artist": "Ed Sheeran", "genre": "pop", "musical_key": "D", "tempo": 79, "energy": 2, "duration_seconds": 281, "notes": "First dance option"},
    # Jazz (5)
    {"title": "Fly Me to the Moon", "artist": "Frank Sinatra", "genre": "jazz", "musical_key": "C", "tempo": 120, "energy": 3, "duration_seconds": 150, "notes": "Standard"},
    {"title": "All of Me", "artist": "John Legend", "genre": "jazz", "musical_key": "Ab", "tempo": 63, "energy": 2, "duration_seconds": 270, "notes": "Modern classic"},
    {"title": "Take Five", "artist": "Dave Brubeck", "genre": "jazz", "musical_key": "Ebm", "tempo": 172, "energy": 3, "duration_seconds": 325, "notes": "5/4 time"},
    {"title": "Autumn Leaves", "artist": "Nat King Cole", "genre": "jazz", "musical_key": "Gm", "tempo": 110, "energy": 2, "duration_seconds": 200, "notes": ""},
    {"title": "So What", "artist": "Miles Davis", "genre": "jazz", "musical_key": "Dm", "tempo": 136, "energy": 3, "duration_seconds": 545, "notes": "Modal jazz"},
    # Blues (4)
    {"title": "The Thrill Is Gone", "artist": "B.B. King", "genre": "blues", "musical_key": "Bm", "tempo": 88, "energy": 3, "duration_seconds": 320, "notes": ""},
    {"title": "Pride and Joy", "artist": "Stevie Ray Vaughan", "genre": "blues", "musical_key": "E", "tempo": 122, "energy": 4, "duration_seconds": 218, "notes": "Texas shuffle"},
    {"title": "Crossroads", "artist": "Cream", "genre": "blues", "musical_key": "A", "tempo": 130, "energy": 5, "duration_seconds": 255, "notes": ""},
    {"title": "Stormy Monday", "artist": "T-Bone Walker", "genre": "blues", "musical_key": "G", "tempo": 72, "energy": 2, "duration_seconds": 280, "notes": "Slow blues"},
    # Country (3)
    {"title": "Wagon Wheel", "artist": "Darius Rucker", "genre": "country", "musical_key": "G", "tempo": 150, "energy": 4, "duration_seconds": 262, "notes": "Sing-along"},
    {"title": "Jolene", "artist": "Dolly Parton", "genre": "country", "musical_key": "Cm", "tempo": 112, "energy": 3, "duration_seconds": 162, "notes": ""},
    {"title": "Ring of Fire", "artist": "Johnny Cash", "genre": "country", "musical_key": "G", "tempo": 108, "energy": 3, "duration_seconds": 158, "notes": ""},
    # Soul / R&B (3)
    {"title": "Superstition", "artist": "Stevie Wonder", "genre": "soul", "musical_key": "Ebm", "tempo": 100, "energy": 5, "duration_seconds": 245, "notes": ""},
    {"title": "Ain't No Sunshine", "artist": "Bill Withers", "genre": "soul", "musical_key": "Am", "tempo": 76, "energy": 2, "duration_seconds": 122, "notes": ""},
    {"title": "Let's Stay Together", "artist": "Al Green", "genre": "r_and_b", "musical_key": "F", "tempo": 104, "energy": 3, "duration_seconds": 198, "notes": "Ceremony option"},
    # Latin (2)
    {"title": "Besame Mucho", "artist": "Consuelo Velazquez", "genre": "latin", "musical_key": "Dm", "tempo": 100, "energy": 3, "duration_seconds": 210, "notes": "Bilingual version"},
    {"title": "Despacito", "artist": "Luis Fonsi", "genre": "latin", "musical_key": "Bm", "tempo": 89, "energy": 4, "duration_seconds": 229, "notes": ""},
    # Funk (2)
    {"title": "September", "artist": "Earth Wind & Fire", "genre": "funk", "musical_key": "Ab", "tempo": 126, "energy": 5, "duration_seconds": 215, "notes": "Party closer"},
    {"title": "Get Lucky", "artist": "Daft Punk", "genre": "funk", "musical_key": "F#m", "tempo": 116, "energy": 4, "duration_seconds": 249, "notes": ""},
    # Folk (1)
    {"title": "Hallelujah", "artist": "Leonard Cohen", "genre": "folk", "musical_key": "C", "tempo": 56, "energy": 1, "duration_seconds": 282, "notes": "Acoustic arrangement"},
]


def seed():
    with app.app_context():
        password_hash = generate_password_hash("demo123")

        with get_db(immediate=True) as db:
            # 1. Create demo musician
            user_id = create_user(db, "demo@giglist.com", password_hash, "Demo Musician")
            print(f"Created user: Demo Musician (id={user_id})")

            # 2. Create 30 songs
            song_ids = []
            for song_data in SONGS:
                song_id = create_song(
                    db,
                    user_id,
                    song_data["title"],
                    song_data["artist"],
                    song_data["genre"],
                    song_data["musical_key"],
                    song_data["tempo"],
                    song_data["energy"],
                    song_data["duration_seconds"],
                    song_data["notes"],
                )
                song_ids.append(song_id)
            print(f"Created {len(song_ids)} songs")

            # 3. Create 2 events with portal tokens
            wedding_token = secrets.token_urlsafe(32)
            wedding_id = create_event(
                db,
                user_id,
                "Smith-Jones Wedding",
                "2026-07-12",
                "wedding",
                "Rosewood Estate",
                "Sarah Smith",
                "sarah@example.com",
                wedding_token,
                notes="Reception starts at 6 PM, ceremony at 4 PM",
            )
            print(f"Created event: Smith-Jones Wedding (id={wedding_id}, token={wedding_token})")

            corporate_token = secrets.token_urlsafe(32)
            corporate_id = create_event(
                db,
                user_id,
                "TechCorp Annual Gala",
                "2026-09-20",
                "corporate",
                "Grand Ballroom Hotel",
                "Mike Chen",
                "mike@techcorp.example.com",
                corporate_token,
                notes="Formal event, 200 guests",
            )
            print(f"Created event: TechCorp Annual Gala (id={corporate_id}, token={corporate_token})")

            # 4. Create 10 playlist items for the wedding event
            #    Mix of must_play, do_not_play, and normal items
            wedding_playlist = [
                # (song index, is_must_play, is_do_not_play, client_note)
                (9, 1, 0, "Our first dance song!"),         # Thinking Out Loud
                (3, 0, 0, ""),                              # Roxanne
                (10, 0, 0, "Cocktail hour"),                # Fly Me to the Moon
                (24, 1, 0, "Please play during dinner"),    # Let's Stay Together
                (5, 1, 0, "Must play for dance floor"),     # Uptown Funk
                (19, 0, 0, ""),                             # Wagon Wheel
                (27, 0, 0, "Party time!"),                  # September
                (4, 0, 1, "Groom hates this song"),         # Under the Bridge
                (29, 0, 0, ""),                             # Hallelujah
                (22, 0, 1, "Too loud for this event"),      # Superstition
            ]

            for position, (song_idx, must_play, dnp, note) in enumerate(wedding_playlist):
                item_id = add_playlist_item(db, wedding_id, song_ids[song_idx], position)
                # Set flags and notes via direct SQL since the model functions
                # toggle_playlist_flag and add_playlist_item don't support setting
                # these at creation time
                if must_play or dnp or note:
                    db.execute(
                        "UPDATE playlist_item SET is_must_play = ?, is_do_not_play = ?, client_note = ? WHERE id = ?",
                        (must_play, dnp, note, item_id),
                    )
            print(f"Created {len(wedding_playlist)} playlist items for wedding")

            # 5. Create 3 song requests for the wedding event
            add_song_request(
                db,
                wedding_id,
                "Can't Help Falling in Love",
                "Elvis Presley",
                "Would love this for the father-daughter dance",
            )
            add_song_request(
                db,
                wedding_id,
                "Crazy in Love",
                "Beyonce",
                "",
            )
            add_song_request(
                db,
                wedding_id,
                "Sweet Caroline",
                "Neil Diamond",
                "Everyone loves singing along to this one",
            )
            print("Created 3 song requests for wedding")

            db.commit()

        print("\nSeed complete!")
        print(f"  Login: demo@giglist.com / demo123")
        print(f"  Wedding portal: /portal/{wedding_token}")
        print(f"  Corporate portal: /portal/{corporate_token}")


if __name__ == "__main__":
    seed()
