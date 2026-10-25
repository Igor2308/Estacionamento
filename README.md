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
5. **Entradas e saídas** – a entrada só aceita placas cadastradas. **Horista** usa as vagas rotativas do tipo do veículo e a saída calcula o valor. **Mensalista** precisa ter vaga vinculada para o tipo do veículo e **cada vaga comporta um veículo do cliente por vez** (com 2 vagas de carro entram 2 carros; o terceiro é barrado até um sair). A saída do mensalista só libera a vaga, sem cobrança. A aba *Cancelar plano mensal* encerra o plano **vaga por vaga**, e só quando não há mensalidade em aberto e o veículo não está no estacionamento.
6. **Pagamentos** – horista (após a saída), mensalidade ou outro. Ao vincular vagas a um mensalista a mensalidade de cada vaga já nasce em aberto (e novas a cada mês); o cliente paga **de uma vez o valor de todas as vagas do mesmo período** (2 vagas = 2 mensalidades somadas). Em dinheiro, informa-se o valor recebido e o troco é calculado.

## Como as telas se comportam

- **Formulários em sequência:** em cada cadastro só o primeiro campo começa habilitado; o próximo só libera quando o anterior estiver válido, e o erro aparece embaixo do próprio campo. Telefone, CPF/CNPJ, CEP, UF e número só aceitam o que faz sentido (sem letras onde não pode) e têm tamanho máximo. A mesma validação existe no servidor.
- **CEP:** no Brasil, ao digitar um CEP válido o endereço é buscado no ViaCEP (a tela precisa de internet; sem ela, o endereço é digitado à mão). O endereço tem o campo **País**.
- **Listas paginadas:** 50 registros por página; só a página pedida é carregada. Há campo de busca acima de cada lista (clientes: nome ou CPF/CNPJ; veículos: placa, cliente ou CPF; vagas: código, setor ou cliente…). As rotas de listagem sem `?pagina=` continuam devolvendo tudo.
- **Cliente mensalista:** ao escolher "Mensalista" informa-se a **quantidade de vagas** e seleciona-se cada uma (só vagas livres) já no cadastro; a mensalidade de todas fica em aberto em Pagamentos.
- **Painel inicial:** botões de ação no topo (novo cliente, novo veículo, nova vaga, registrar entrada, registrar saída, pagamento), números do dia e os cinco tipos de veículo na mesma linha. Vaga de mensalista só conta como ocupada quando há veículo dentro.
- **Edição de cliente:** dados e endereços abrem juntos no topo; CPF/CNPJ e tipo de pessoa não são editáveis (só direto no banco).
- **Avisos e confirmações** usam modais (nada de alert/confirm/prompt do navegador).
- **Quem registrou e quando** aparece nas listas de veículos, vagas, entradas/saídas, tarifas e pagamentos (o log completo fica para depois).
- **Pagamento em dinheiro:** informa-se o valor recebido; o troco é calculado, guardado, e a tela mostra o dinheiro físico do dia (recebido, troco devolvido, ficou no caixa).

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
