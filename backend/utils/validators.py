"""Validações reutilizáveis (placa, CPF, CNPJ e datas)."""
import re
from datetime import date

TIPOS_VEICULO = ("CARRO", "MOTO", "VAN", "CAMINHAO", "OUTRO")
ROTULO_TIPO = {"CARRO": "carro", "MOTO": "moto", "VAN": "van", "CAMINHAO": "caminhão", "OUTRO": "outro"}

_PLACA = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")  # antiga (ABC1234) e Mercosul (ABC1D23)


def somente_digitos(valor):
    return re.sub(r"\D", "", valor) if isinstance(valor, str) else ""


def normalizar_placa(placa):
    return re.sub(r"[\s\-]", "", placa).upper() if isinstance(placa, str) else ""


def validar_placa(placa):
    return bool(_PLACA.match(normalizar_placa(placa)))


def _digito(base, pesos):
    resto = sum(int(d) * p for d, p in zip(base, pesos)) % 11
    return "0" if resto < 2 else str(11 - resto)


def validar_cpf(cpf):
    cpf = somente_digitos(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    d1 = _digito(cpf[:9], range(10, 1, -1))
    d2 = _digito(cpf[:9] + d1, range(11, 1, -1))
    return cpf[9:] == d1 + d2


def validar_cnpj(cnpj):
    cnpj = somente_digitos(cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = _digito(cnpj[:12], p1)
    d2 = _digito(cnpj[:12] + d1, [6] + p1)
    return cnpj[12:] == d1 + d2


def validar_data(texto):
    """Converte 'AAAA-MM-DD' em date; retorna None se for inválida."""
    try:
        return date.fromisoformat(texto) if isinstance(texto, str) else None
    except ValueError:
        return None


def validar_telefone(telefone):
    """Telefone brasileiro com DDD: 10 ou 11 dígitos."""
    return len(somente_digitos(telefone)) in (10, 11)


def validar_cep(cep):
    return len(somente_digitos(cep)) == 8


_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validar_email(email):
    return isinstance(email, str) and bool(_EMAIL.match(email.strip()))
