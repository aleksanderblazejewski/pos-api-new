from flask_api.extensions import db
from datetime import date, time


# =========================
# STAFF
# =========================

class Pracownicy(db.Model):
    __tablename__ = "Pracownicy"
    ID = db.Column(db.Integer, primary_key=True)
    Numer_prac = db.Column(db.Integer, nullable=False)
    Nazwisko = db.Column(db.String(50), nullable=False)
    Imie = db.Column(db.String(50), nullable=False)
    Tel = db.Column(db.String(20), nullable=False)


# =========================
# ZONES (STREFY)
# =========================

class Strefa(db.Model):
    __tablename__ = "Strefa"
    ID = db.Column(db.Integer, primary_key=True)
    Nazwa = db.Column(db.String(20), nullable=False)


# =========================
# TABLES (STOLIKI)
# =========================

class Stoliki(db.Model):
    __tablename__ = "Stoliki"
    ID = db.Column(db.Integer, primary_key=True)
    Numer = db.Column(db.Integer, nullable=False)
    Ile_osob = db.Column(db.Integer, nullable=False)
    Strefa_ID = db.Column(db.Integer, db.ForeignKey("Strefa.ID"), nullable=False)

    # MANY-TO-MANY: Stoliki <-> Strefa
    strefy = db.relationship(
        "Strefa",
        secondary="Stoliki_Strefy",
        backref=db.backref("stoliki", lazy="dynamic"),
        lazy="joined"
    )


class StolikiStrefy(db.Model):
    __tablename__ = "Stoliki_Strefy"

    Stoliki_ID = db.Column(db.Integer, db.ForeignKey("Stoliki.ID"), primary_key=True)
    Strefa_ID = db.Column(db.Integer, db.ForeignKey("Strefa.ID"), primary_key=True)


class MapaStolikow(db.Model):
    __tablename__ = "MapaStolikow"
    ID = db.Column(db.Integer, primary_key=True)
    Stoliki_ID = db.Column(db.Integer, db.ForeignKey("Stoliki.ID"), nullable=False, unique=True)
    X_Pos = db.Column(db.Integer)
    Y_Pos = db.Column(db.Integer)
    Rotation = db.Column(db.Integer)
    Nazwa = db.Column(db.String(255), nullable=False)
    Poziom = db.Column(db.Integer, nullable=False, server_default="0")


# =========================
# WAITERS (KELNERZY)
# =========================

class Kelnerzy(db.Model):
    __tablename__ = "Kelnerzy"
    ID = db.Column(db.Integer, primary_key=True)
    Pracownicy_ID = db.Column(db.Integer, db.ForeignKey("Pracownicy.ID"), nullable=False, unique=True)
    Strefa_ID = db.Column(db.Integer, db.ForeignKey("Strefa.ID"), nullable=False)

    # MANY-TO-MANY: Kelnerzy <-> Strefa
    strefy = db.relationship(
        "Strefa",
        secondary="Kelnerzy_Strefy",
        backref=db.backref("kelnerzy", lazy="dynamic"),
        lazy="joined"
    )


class KelnerzyStrefy(db.Model):
    __tablename__ = "Kelnerzy_Strefy"

    Kelnerzy_ID = db.Column(db.Integer, db.ForeignKey("Kelnerzy.ID"), primary_key=True)
    Strefa_ID = db.Column(db.Integer, db.ForeignKey("Strefa.ID"), primary_key=True)


# =========================
# LOGIN/SETTINGS
# =========================

class Logowanie(db.Model):
    __tablename__ = "Logowanie"
    ID = db.Column(db.Integer, primary_key=True)
    Pracownicy_ID = db.Column(db.Integer, db.ForeignKey("Pracownicy.ID"), nullable=False, unique=True)
    Login = db.Column(db.String(255), nullable=False)
    Haslo = db.Column(db.String(255), nullable=False)
    Sol = db.Column(db.String(255), nullable=False, default="")


class Ustawienia(db.Model):
    __tablename__ = "Ustawienia"

    ID = db.Column(db.Integer, primary_key=True)

    # np. "Zatwierdzanie_Rezerwacji", "Odstep_miedzy_rezerwacjami", ...
    Nazwa_opcji = db.Column(db.String(120), nullable=False, unique=True)

    # trzymamy jako tekst; typ mówi jak interpretować (int/bool/time/string)
    Wartosc = db.Column(db.String(255), nullable=False)

    # np. "bool", "int", "time", "string"
    Typ = db.Column(db.String(30), nullable=True)

    Opis = db.Column(db.String(255), nullable=True)



# =========================
# MENU
# =========================

class Menu(db.Model):
    __tablename__ = "Menu"
    ID = db.Column(db.Integer, primary_key=True)
    Nazwa = db.Column(db.String(100), nullable=False)
    Cena = db.Column(db.Numeric(6, 2), nullable=False)
    Opis = db.Column(db.String(255), nullable=False)
    Alergeny = db.Column(db.String(255))


# =========================
# ORDERS
# =========================

class Zamowienia(db.Model):
    __tablename__ = "Zamowienia"
    ID = db.Column(db.Integer, primary_key=True)
    Data = db.Column(db.DateTime, nullable=False)
    Status = db.Column(db.String(20), nullable=False)
    Uwagi = db.Column(db.String(255))
    Kelnerzy_ID = db.Column(db.Integer, db.ForeignKey("Kelnerzy.ID"), nullable=False)
    Stoliki_ID = db.Column(db.Integer, db.ForeignKey("Stoliki.ID"), nullable=False)


class Zam_Poz(db.Model):
    __tablename__ = "Zam_Poz"
    ID = db.Column(db.Integer, primary_key=True)
    Zamowienia_ID = db.Column(db.Integer, db.ForeignKey("Zamowienia.ID"), nullable=False)
    Menu_ID = db.Column(db.Integer, db.ForeignKey("Menu.ID"), nullable=False)
    Ilosc = db.Column(db.Integer, nullable=False)
    Wydane = db.Column(db.String(1), nullable=False)


# =========================
# RESERVATIONS
# =========================

class Rezerwacje(db.Model):
    __tablename__ = "Rezerwacje"

    ID = db.Column(db.Integer, primary_key=True)

    Imie = db.Column(db.String(60), nullable=False)
    Nazwisko = db.Column(db.String(80), nullable=False)
    Tel = db.Column(db.String(20), nullable=True)

    Ilosc_osob = db.Column(db.Integer, nullable=False)

    Data = db.Column(db.Date, nullable=False)
    Godzina = db.Column(db.Time, nullable=False)

    Zatwierdzone = db.Column(db.Boolean, nullable=False, default=False)

    Stoliki_ID = db.Column(db.Integer, db.ForeignKey("Stoliki.ID"), nullable=True)


class Magazyn(db.Model):
    __tablename__ = "Magazyn"
    ID = db.Column(db.Integer, primary_key=True)
    Nazwa = db.Column(db.String(255), nullable=False)
    Jednostka = db.Column(db.String(50), nullable=False)
    Ilosc = db.Column(db.Numeric(12, 3), nullable=False)
