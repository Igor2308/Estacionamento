# Projeto_Estacionamento: testes iniciais

## Instalar dependências

No terminal do VS Code, na pasta raiz do projeto:

```bash
python -m pip install -r requirements.txt
```

## Rodar os testes

Ainda na pasta raiz:

```bash
python -m pytest tests/ -v
```

Os testes incluídos verificam inicialização da API, registro das rotas principais e validações que devem falhar antes de abrir conexão com o MySQL. Eles **não** substituem os testes de integração com um banco de teste.

## Configuração

Mantenha seu `.env` local fora do ZIP e do controle de versão. O backend espera `FLASK_SECRET_KEY`, `DB_NAME`, `DB_USER` e as configurações de conexão do MySQL. Não use a chave exclusiva dos testes em produção.
