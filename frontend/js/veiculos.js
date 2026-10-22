const $ = id => document.getElementById(id);
const TIPOS = { CARRO: "Carro", MOTO: "Moto", VAN: "Van", CAMINHAO: "Caminhão", OUTRO: "Outro" };
let veiculos = [], editando = null;

const opcoes = (lista, id, rotulo, vazio) =>
  `<option value="">${vazio}</option>` + lista.map(x => `<option value="${x[id]}">${esc(rotulo(x))}</option>`).join("");

/* ---------- listas (marca / modelo / cor) ---------- */
async function carregarClientes(selecionar) {
  const r = await acao(() => api("/clientes")); if (!r) return;
  const ativos = r.dados.filter(c => c.ativo);
  $("cliente").innerHTML = opcoes(ativos, "id_cliente", c => c.nome + " — " + (c.cpf || c.cnpj || "sem documento"), ativos.length ? "Selecione o cliente..." : "Cadastre um cliente antes");
  if (selecionar) $("cliente").value = selecionar;
}
async function carregarMarcas(selecionar) {
  const r = await acao(() => api("/marcas")); if (!r) return;
  $("marca").innerHTML = opcoes(r.dados, "id_marca", x => x.nome, "Selecione...");
  if (selecionar) $("marca").value = selecionar;
}
async function carregarModelos(selecionar) {
  const marca = $("marca").value;
  $("modelo").disabled = $("novoModelo").disabled = !marca;
  if (!marca) { $("modelo").innerHTML = '<option value="">Escolha a marca primeiro</option>'; return; }
  const r = await acao(() => api("/modelos?id_marca=" + marca)); if (!r) return;
  $("modelo").innerHTML = opcoes(r.dados, "id_modelo", x => x.nome, "Selecione...");
  if (selecionar) $("modelo").value = selecionar;
}
async function carregarCores(selecionar) {
  const r = await acao(() => api("/cores")); if (!r) return;
  $("cor").innerHTML = opcoes(r.dados, "id_cor", x => x.nome, "Selecione...");
  if (selecionar) $("cor").value = selecionar;
}

/* cadastra um item novo na lista e já deixa selecionado (se já existir, só seleciona) */
async function novoItem(rotulo, caminho, corpoExtra, campoId, recarregar) {
  const nome = prompt(`Nome da nova ${rotulo}:`);
  if (!nome || !nome.trim()) return;
  const r = await acao(() => api(caminho, { metodo: "POST", corpo: { ...corpoExtra, nome } }));
  if (!r) return;
  aviso(r.ja_existia ? `"${r.nome}" já estava cadastrada — selecionei para você.` : `"${r.nome}" cadastrada e selecionada.`);
  await recarregar(r[campoId]);
}
$("novaMarca").onclick = async () => { await novoItem("marca", "/marcas", {}, "id_marca", carregarMarcas); await carregarModelos(); };
$("novoModelo").onclick = () => {
  if (!$("marca").value) return aviso("Escolha a marca antes de cadastrar o modelo.", "erro");
  novoItem("modelo", "/modelos", { id_marca: Number($("marca").value) }, "id_modelo", carregarModelos);
};
$("novaCor").onclick = () => novoItem("cor", "/cores", {}, "id_cor", carregarCores);
$("marca").onchange = () => carregarModelos();

/* ---------- lista de veículos ---------- */
async function carregar() {
  const r = await acao(() => api("/veiculos")); if (!r) return;
  veiculos = r.dados;
  $("lista").innerHTML = veiculos.length ? veiculos.map(v => `<tr>
    <td><b>${esc(v.placa)}</b></td><td>${esc(v.nome_cliente)}</td><td>${TIPOS[v.tipo_veiculo] || esc(v.tipo_veiculo)}</td>
    <td>${esc([v.marca, v.modelo].filter(Boolean).join(" ") || "—")}</td><td>${esc(v.cor || "—")}</td>
    <td><span class="tag ${v.ativo ? "ok" : "off"}">${v.ativo ? "Ativo" : "Inativo"}</span></td>
    <td><button class="mini sec" data-a="editar" data-id="${v.id_veiculo}">Editar</button>
        <button class="mini ${v.ativo ? "perigo" : "sec"}" data-a="${v.ativo ? "desativar" : "reativar"}" data-id="${v.id_veiculo}">${v.ativo ? "Desativar" : "Reativar"}</button></td></tr>`).join("")
    : linhasVazias(7, "Nenhum veículo cadastrado.");
}

$("lista").onclick = async e => {
  const b = e.target.closest("button"); if (!b) return;
  const id = Number(b.dataset.id), v = veiculos.find(x => x.id_veiculo === id);
  if (b.dataset.a === "editar") {
    editando = id; $("tituloForm").textContent = "Editando: " + v.placa; $("salvar").textContent = "Salvar alterações";
    $("cancelar").classList.remove("oculto");
    $("cliente").value = v.id_cliente; $("cliente").disabled = true; // o dono do veículo não muda por aqui
    $("placa").value = v.placa; $("tipo").value = v.tipo_veiculo;
    $("marca").value = v.id_marca || ""; await carregarModelos(v.id_modelo); $("cor").value = v.id_cor || "";
    scrollTo({ top: 0, behavior: "smooth" });
  } else if (b.dataset.a === "desativar") {
    if (!confirm("Desativar o veículo " + v.placa + "?")) return;
    if (await acao(() => api("/veiculos/" + id, { metodo: "DELETE" }), "Veículo desativado.")) carregar();
  } else {
    if (await acao(() => api("/veiculos/" + id, { metodo: "PUT", corpo: { ativo: true } }), "Veículo reativado.")) carregar();
  }
};

function cancelarEdicao() {
  editando = null; $("form").reset(); $("cliente").disabled = false; carregarModelos();
  $("tituloForm").textContent = "Novo veículo"; $("salvar").textContent = "Salvar veículo"; $("cancelar").classList.add("oculto");
}
$("cancelar").onclick = cancelarEdicao;

$("form").onsubmit = async e => {
  e.preventDefault();
  const falta = [["cliente", "o cliente"], ["placa", "a placa"], ["marca", "a marca"], ["modelo", "o modelo"], ["cor", "a cor"]]
    .find(([id]) => !String($(id).value).trim());
  if (falta) { $(falta[0]).focus(); return aviso("Informe " + falta[1] + ".", "erro"); }
  const corpo = {
    placa: $("placa").value.trim(), tipo_veiculo: $("tipo").value,
    id_marca: Number($("marca").value), id_modelo: Number($("modelo").value), id_cor: Number($("cor").value),
  };
  let r;
  if (editando) r = await acao(() => api("/veiculos/" + editando, { metodo: "PUT", corpo }), "Veículo atualizado.");
  else { corpo.id_cliente = Number($("cliente").value); r = await acao(() => api("/veiculos", { metodo: "POST", corpo }), "Veículo cadastrado."); }
  if (r) { cancelarEdicao(); carregar(); }
};

(async () => {
  await iniciarPagina("veiculos");
  const pre = Number(new URLSearchParams(location.search).get("cliente")) || null;
  await Promise.all([carregarClientes(pre), carregarMarcas(), carregarCores()]);
  await carregarModelos(); carregar();
})();
