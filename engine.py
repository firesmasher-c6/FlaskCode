import sqlite3
import re
import random
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge.db")

END_TOKEN = "<END>"

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "doing", "what", "how", "why", "where", "who",
    "which", "that", "this", "these", "those", "it", "its", "you", "your",
    "i", "me", "my", "we", "our", "and", "or", "but", "of", "to", "in",
    "on", "for", "with", "about", "at", "as", "by", "from", "tell", "me",
}

SEED_CORPUS = [
    "the world is full of strange and wonderful things",
    "the mind is a pattern that learns from itself",
    "the future is written one choice at a time",
    "the night sky holds more questions than stars",
    "the simplest ideas are often the strongest",
    "the more you learn the less you assume",
    "the past cannot be changed but it can be understood",
    "a machine can learn but it cannot dream",
    "a story is only as good as its silence",
    "a question without curiosity rarely finds an answer",
    "a single word can carry the weight of a thousand thoughts",
    "every sentence begins with a single word",
    "every question deserves an honest answer",
    "every pattern hides a deeper pattern underneath",
    "every idea starts as a small and fragile thing",
    "knowledge grows the more you share it",
    "knowledge without patience becomes noise",
    "language is the mirror of the mind",
    "language shapes the way we think about the world",
    "silence can say more than a thousand words",
    "silence is where the best ideas are born",
    "curiosity is the engine of discovery",
    "curiosity keeps the mind young and restless",
    "time moves forward whether we are ready or not",
    "time reveals what patience cannot always explain",
    "words are the bricks that build every thought",
    "words carry meaning long after they are spoken",
    "understanding comes slowly and leaves quickly",
    "understanding grows when questions are welcomed",
    "patience is a quiet kind of strength",
    "patience turns small steps into real progress",
    "memory fades but patterns remain",
    "memory is a story we tell ourselves again and again",
    "learning never truly ends it only slows down",
    "learning is a conversation between curiosity and patience",
    "i think therefore i am",
    "i learn from every word you give me",
    "code is a language built from logic and patience",
    "code becomes clearer the more it is understood",
    "a machine that listens is not the same as a machine that understands",
    "a computer only knows what it has been taught",
    "thought is a chain of small connected ideas",
    "thought without language is only a shadow of an idea",
    "dreams are patterns the mind builds when it rests",
    "the stars remind us how small our questions really are",
    "questions are the seeds that curiosity plants",
    "answers are only useful when the question was honest",
    "the future belongs to those who keep asking questions",
    "a pattern repeated enough becomes a kind of truth",
    "every conversation teaches something if you are listening",

    "hello there how are you today",
    "hi it is good to see you again",
    "good morning i hope you slept well",
    "good evening how was your day",
    "nice to meet you what is your name",
    "how are you doing this afternoon",
    "i am doing well thank you for asking",
    "what have you been up to lately",
    "long time no see how have you been",
    "it is a pleasure to talk with you",

    "the weather today is warm and sunny",
    "it looks like rain is coming later tonight",
    "the wind is strong and the sky is gray",
    "winter brings cold mornings and short days",
    "summer afternoons are long and full of light",
    "the clouds are moving fast across the sky",
    "spring brings new flowers and warmer air",
    "autumn leaves fall slowly to the ground",

    "computers process information faster than the human brain",
    "software is a set of instructions a computer follows",
    "artificial intelligence learns patterns from large amounts of data",
    "the internet connects millions of computers around the world",
    "a good programmer writes code that other people can read",
    "debugging is the process of finding and fixing errors",
    "open source software is built and shared by many people",
    "a database stores information so it can be found later",
    "algorithms are step by step instructions for solving a problem",
    "hardware and software work together to run a program",

    "cooking a good meal takes time and patience",
    "fresh bread smells wonderful when it comes out of the oven",
    "coffee in the morning helps many people wake up",
    "a balanced diet includes fruits vegetables and whole grains",
    "sharing a meal with friends makes the food taste better",
    "spices can turn a simple dish into something special",

    "a good plan makes a hard task feel manageable",
    "taking breaks during work helps the mind stay sharp",
    "deadlines can create pressure but also focus",
    "teamwork makes large projects easier to finish",
    "clear communication prevents most misunderstandings at work",
    "small consistent effort adds up over time",

    "happiness often comes from small simple moments",
    "it is okay to feel sad sometimes",
    "gratitude can change the way you see your day",
    "laughter is one of the best ways to connect with people",
    "confidence grows when you practice something often",
    "kindness costs nothing but means everything",

    "life is full of small moments that matter",
    "every day is a chance to learn something new",
    "the best time to start is usually right now",
    "growing older brings new perspective on old problems",
    "memories connect the past to the present",
    "the present moment is the only one we truly have",

    "the ocean is home to countless forms of life",
    "mountains stand quiet through every kind of weather",
    "forests are full of sounds if you stop and listen",
    "rivers carve their path over thousands of years",
    "animals adapt to survive in their environment",
    "the stars have guided travelers for thousands of years",

    "gravity pulls objects toward the center of the earth",
    "atoms are the building blocks of all matter",
    "energy cannot be created or destroyed only changed",
    "evolution explains how species change over long periods of time",
    "the human body is made of trillions of cells",
    "light travels faster than anything else in the universe",

    "i think that is a really interesting question",
    "in my opinion patience is the most useful skill",
    "that sounds like a great plan to me",
    "i am not sure but i would like to find out",
    "that is one way to look at it",
    "i agree that practice makes a big difference",

    "tomorrow is a good day to try something new",
    "next week i plan to focus on learning",
    "someday i would like to understand this better",
    "later today i will think about what you said",

    "sometimes the simplest jokes are the funniest ones",
    "laughing at yourself is a useful skill",
    "a good sense of humor makes hard days easier",

    "what do you think about that",
    "how does that make you feel",
    "why do you think that happened",
    "what would you do in that situation",
    "where do you think this is going",

    "let me think about that for a moment",
    "that is a good point i had not considered",
    "i want to understand more about what you mean",
    "there are many ways to think about this",
    "every answer leads to another question",
]


class KnowledgeEngine:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _create_tables(self):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS words (
                word TEXT PRIMARY KEY,
                freq INTEGER DEFAULT 1
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chain (
                w1 TEXT NOT NULL,
                w2 TEXT NOT NULL,
                weight INTEGER DEFAULT 1,
                PRIMARY KEY (w1, w2)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chain2 (
                w1 TEXT NOT NULL,
                w2 TEXT NOT NULL,
                w3 TEXT NOT NULL,
                weight INTEGER DEFAULT 1,
                PRIMARY KEY (w1, w2, w3)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS starters (
                word TEXT PRIMARY KEY,
                weight INTEGER DEFAULT 1
            )
        """)
        conn.commit()
        conn.close()

    def _init_db(self):
        first_run = not os.path.exists(self.db_path)
        self._create_tables()
        if first_run:
            self.learn_bulk(SEED_CORPUS)

    def reset(self):
        conn = self._connect()
        cur = conn.cursor()
        for table in ("words", "chain", "chain2", "starters"):
            cur.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
        conn.close()
        self._create_tables()
        self.learn_bulk(SEED_CORPUS)

    @staticmethod
    def _tokenize(text: str):
        text = text.lower().strip()
        text = re.sub(r"[^a-z0-9'\s]", "", text)
        return [w for w in text.split() if w]

    def learn(self, sentence: str):
        words = self._tokenize(sentence)
        if not words:
            return
        conn = self._connect()
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO starters (word, weight) VALUES (?, 1) "
            "ON CONFLICT(word) DO UPDATE SET weight = weight + 1",
            (words[0],)
        )

        for w in words:
            cur.execute(
                "INSERT INTO words (word, freq) VALUES (?, 1) "
                "ON CONFLICT(word) DO UPDATE SET freq = freq + 1",
                (w,)
            )

        for i in range(len(words) - 1):
            w1, w2 = words[i], words[i + 1]
            cur.execute(
                "INSERT INTO chain (w1, w2, weight) VALUES (?, ?, 1) "
                "ON CONFLICT(w1, w2) DO UPDATE SET weight = weight + 1",
                (w1, w2)
            )

        cur.execute(
            "INSERT INTO chain (w1, w2, weight) VALUES (?, ?, 1) "
            "ON CONFLICT(w1, w2) DO UPDATE SET weight = weight + 1",
            (words[-1], END_TOKEN)
        )

        if len(words) >= 2:
            for i in range(len(words) - 2):
                w1, w2, w3 = words[i], words[i + 1], words[i + 2]
                cur.execute(
                    "INSERT INTO chain2 (w1, w2, w3, weight) VALUES (?, ?, ?, 1) "
                    "ON CONFLICT(w1, w2, w3) DO UPDATE SET weight = weight + 1",
                    (w1, w2, w3)
                )
            cur.execute(
                "INSERT INTO chain2 (w1, w2, w3, weight) VALUES (?, ?, ?, 1) "
                "ON CONFLICT(w1, w2, w3) DO UPDATE SET weight = weight + 1",
                (words[-2], words[-1], END_TOKEN)
            )

        conn.commit()
        conn.close()

    def learn_bulk(self, sentences):
        for s in sentences:
            self.learn(s)

    def _weighted_pick(self, rows):
        total = sum(w for _, w in rows)
        r = random.uniform(0, total)
        upto = 0
        for word, weight in rows:
            upto += weight
            if upto >= r:
                return word
        return rows[-1][0]

    def _random_starter(self):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT word, weight FROM starters")
        rows = cur.fetchall()
        conn.close()
        if not rows:
            return None
        return self._weighted_pick(rows)

    def _next_word(self, current: str):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT w2, weight FROM chain WHERE w1 = ?", (current,))
        rows = cur.fetchall()
        conn.close()
        if not rows:
            return END_TOKEN
        return self._weighted_pick(rows)

    def _next_word2(self, w1: str, w2: str):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT w3, weight FROM chain2 WHERE w1 = ? AND w2 = ?", (w1, w2))
        rows = cur.fetchall()
        conn.close()
        if not rows:
            return None
        return self._weighted_pick(rows)

    def find_seed(self, message: str):
        words = self._tokenize(message)
        if not words:
            return None
        conn = self._connect()
        cur = conn.cursor()
        candidates = []
        seen = set()
        for w in words:
            if w in seen:
                continue
            seen.add(w)
            cur.execute("SELECT word, freq FROM words WHERE word = ?", (w,))
            row = cur.fetchone()
            if row:
                candidates.append(row)
        conn.close()
        if not candidates:
            return None
        meaningful = [c for c in candidates if c[0] not in STOPWORDS]
        pool = meaningful if meaningful else candidates
        # lowest freq = most topically distinctive (least generic) word
        pool.sort(key=lambda r: r[1])
        top = pool[:3]
        return random.choice(top)[0]

    TRIGRAM_PROBABILITY = 0.55  # unused now, kept for reference
    MAX_VERBATIM_RUN = 5  # force a jump after this many consecutive memorized words

    def generate(self, seed: str = None, max_words: int = 20, min_words: int = 4, attempts: int = 5):
        best_words = None
        current_seed = seed

        for _ in range(attempts):
            start = current_seed if current_seed else self._random_starter()
            if start is None:
                return None

            words = [start]
            second = self._next_word(start)
            if second != END_TOKEN:
                words.append(second)

            trigram_run = 0
            while len(words) < max_words:
                nxt = None
                if len(words) >= 2 and trigram_run < self.MAX_VERBATIM_RUN:
                    nxt = self._next_word2(words[-2], words[-1])

                if nxt is not None:
                    trigram_run += 1
                else:
                    nxt = self._next_word(words[-1])
                    trigram_run = 0

                if nxt == END_TOKEN:
                    break
                words.append(nxt)

            if best_words is None or len(words) > len(best_words):
                best_words = words

            if len(words) >= min_words:
                break

            current_seed = None  # dead end -- try a fresh random starter

        sentence = " ".join(best_words)
        sentence = sentence[0].upper() + sentence[1:]
        return sentence + "."

    def context_for(self, message: str, num_drafts: int = 3):
        seed = self.find_seed(message)
        tokens = self._tokenize(message)
        topic_words = [w for w in dict.fromkeys(tokens) if w not in STOPWORDS]
        drafts = []
        for _ in range(num_drafts):
            d = self.generate(seed=seed)
            if d and d not in drafts:
                drafts.append(d)
        return {"seed": seed, "topic_words": topic_words, "drafts": drafts}

    def stats(self):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM words")
        word_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM chain")
        bigram_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM chain2")
        trigram_count = cur.fetchone()[0]
        conn.close()
        return word_count, bigram_count, trigram_count