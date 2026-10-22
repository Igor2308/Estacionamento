# Sistema de Estacionamento (Flask + MySQL)

## 1. Preparar o banco
```bash
mysql -u SEU_USUARIO -p < banco/schema.sql
mysql -u SEU_USUARIO -p < banco/dados_iniciais.sql   # tarifa inicial (ajuste os valores)
```

### Já tem o banco criado de uma versão anterior?
Não recrie o banco (perderia os dados). Rode uma vez, dentro da pasta `backend`:
```bash
python atualizar_banco.py
```
Ele cria as tabelas de marcas/modelos/cores (aproveitando o que já estava nos veículos), adiciona o **tipo de veículo**
nas tarifas e nas vagas (tarifas antigas viram tarifa de todos os tipos; vagas antigas ficam como "carro") e, se não
houver nenhuma tarifa, cadastra uma inicial para cada tipo. Pode rodar de novo sem problema.

## 2. Configurar o `.env` (na raiz do projeto)
Copie `.env.example` para `.env` e preencha `FLASK_SECRET_KEY`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`.

## 3. Instalar e criar o primeiro usuário
```bash
python -m pip install -r requirements.txt
cd backend
python criar_usuario.py admin "Seu Nome"      # pede a senha no terminal
```

## 4. Rodar
```bash
cd backend
python app.py
```
Abra **http://127.0.0.1:5000/app/html/login.html**

## Login e sessão
- Nenhuma tela abre sem login: quem digita o endereço de uma tela sem estar logado é levado ao login, e a API responde 401.
- A sessão (cookie) acaba ao fechar o navegador e também depois de 30 minutos sem uso (mude com `SESSION_IDLE_MINUTES` no `.env`).
- A sessão vale por **aba**: ao fechar a aba, ou abrir o endereço numa aba nova, o login é pedido de novo.
- Abrir a tela de login (inclusive pela seta "voltar" do navegador) encerra a sessão: é preciso entrar digitando usuário e senha.

## Ordem de uso das telas
1. **Tarifas** – cadastre a tarifa de cada tipo de veículo (sem tarifa do tipo não há saída de horista nem mensalidade).
2. **Vagas** – cadastre as vagas rotativas e as mensalistas, informando para qual tipo de veículo cada uma serve.
3. **Clientes** – todos os campos são obrigatórios (menos e-mail e complemento) e o endereço é salvo junto.
4. **Veículos** – escolha o cliente; marca, modelo e cor vêm de listas (use **+ Nova** para cadastrar o que faltar).
5. **Entradas e saídas** – a entrada (horistas) só aceita placas cadastradas e usa as vagas rotativas do tipo do veículo. A saída tem duas abas: **Horistas** (calcula o valor) e **Mensalistas** (a saída cancela o plano mensal: libera as vagas e o cliente vira horista). Mensalistas não registram entrada; a aba Mensalistas cancela o plano **vaga por vaga**, e só quando não há mensalidade em aberto.
6. **Pagamentos** – horista (após a saída), mensalidade ou outro. Ao vincular uma vaga a um mensalista a mensalidade já nasce em aberto (e uma nova a cada mês); é só escolher qual pagar.

## Testes
```bash
python -m pytest tests -v                      # rápidos, sem banco
```
Testes de integração (precisam de um banco **separado**, cujo nome termine em `_teste`):
```bash
# crie o banco de teste uma vez:
sed 's/banco_estacionamento/banco_estacionamento_teste/g' banco/schema.sql | mysql -u SEU_USUARIO -p
# rode (Linux/macOS):
DB_NAME_TESTE=banco_estacionamento_teste DB_USER=... DB_PASSWORD=... python -m pytest tests -v
# Windows (PowerShell):
$env:DB_NAME_TESTE="banco_estacionamento_teste"; $env:DB_USER="..."; $env:DB_PASSWORD="..."; python -m pytest tests -v
```
Esses testes **apagam os dados** do banco de teste; por segurança só rodam se o nome terminar em `_teste`.

## Estrutura
- `backend/controllers` regras de negócio · `backend/routes` endpoints · `backend/utils` validações e sessão
- `frontend/html|css|js` telas (servidas pelo Flask em `/app/`)
- `banco/` scripts SQL · `tests/` testes
