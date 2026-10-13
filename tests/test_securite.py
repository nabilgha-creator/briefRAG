"""mots de passe (scrypt) et jetons de session"""
import pytest

from backend.auth.securite import (LONGUEUR_MIN_MOT_DE_PASSE, empreinte_jeton, empreinte_valide, generer_jeton,
                                   hacher_mot_de_passe, verifier_mot_de_passe)


def test_mot_de_passe_verifie_avec_son_empreinte() :
    empreinte = hacher_mot_de_passe("un-bon-mot-de-passe")
    assert verifier_mot_de_passe("un-bon-mot-de-passe", empreinte)
    assert not verifier_mot_de_passe("un-autre-mot-de-passe", empreinte)


def test_le_mot_de_passe_n_apparait_pas_dans_l_empreinte() :
    assert "secret-tres-long" not in hacher_mot_de_passe("secret-tres-long")


def test_sel_aleatoire_deux_empreintes_differentes() :
    assert hacher_mot_de_passe("meme-mot-de-passe") != hacher_mot_de_passe("meme-mot-de-passe")


def test_mot_de_passe_trop_court_refuse() :
    with pytest.raises(ValueError) :
        hacher_mot_de_passe("a" * (LONGUEUR_MIN_MOT_DE_PASSE - 1))


@pytest.mark.parametrize("empreinte, attendu", [
    ("scrypt$16384$8$1$c2Vs$ZW1wcmVpbnRl", True),
    ("scrypt$abc", False),
    ("bcrypt$16384$8$1$c2Vs$ZW1wcmVpbnRl", False),
    ("motdepasse-en-clair", False),
    ("scrypt$x$8$1$c2Vs$ZW1wcmVpbnRl", False),
])
def test_format_d_empreinte(empreinte, attendu) :
    assert empreinte_valide(empreinte) is attendu


def test_empreinte_generee_est_valide() :
    assert empreinte_valide(hacher_mot_de_passe("motdepasse-valide"))


def test_empreinte_malformee_ne_leve_pas_d_erreur() :
    assert verifier_mot_de_passe("peu importe", "pas-une-empreinte") is False


def test_jetons_aleatoires_et_empreinte_sha256() :
    jeton = generer_jeton()
    assert jeton != generer_jeton()
    assert len(empreinte_jeton(jeton)) == 64
    assert empreinte_jeton(jeton) == empreinte_jeton(jeton)        # déterministe : sert de clé de recherche
