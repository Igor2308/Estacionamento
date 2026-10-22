const $ = id => document.getElementById(id);
let mensalistas = [];
const TIPOS = { CARRO: "Carro", MOTO: "Moto", VAN: "Van", CAMINHAO: "Caminhão", OUTRO: "Outro" };

async function carregar() {
  const [v, c] = await Promise.all([acao(() => api("/vagas")), acao(() => api("/clientes"))]);
  if (!v || !c) return;
  mensalistas = c.dados.filter(x => x.ativo && x.modalidade === "MENSALISTA");
  const opcoes = mensalistas.map(m => `<option value="${m.id_cliente}">${esc(m.nome)}</option>`).join("");
  $("lista").innerHTML = v.dados.length ? v.dados.map(x => {
    let vinculo = "—";
    if (x.tipo_vaga === "MENSALISTA") {
      vinculo = x.id_cliente
        ? `${esc(x.nome_cliente)} <button class="mini sec" data-a="desvincular" data-id="${x.id_vaga}">Desvincular</button>`
        : (x.ativa && mensalistas.length
          ? `<select id="sel${x.id_vaga}"><option value="">Escolher...</option>${opcoes}</select> <button class="mini" data-a="vincular" data-id="${x.id_vaga}">Vincular</button>`
          : "Livre");
    }
    return `<tr><td>${esc(x.codigo)}</td><td>${esc(x.setor || "—")}</td><td>${x.tipo_vaga === "MENSALISTA" ? "Mensalista" : "Rotativa"}</td>
      <td>${TIPOS[x.tipo_veiculo] || esc(x.tipo_veiculo)}</td><td>${vinculo}</td><td><span class="tag ${x.ativa ? "ok" : "off"}">${x.ativa ? "Ativa" : "Inativa"}</span></td>
      <td><button class="mini ${x.ativa ? "perigo" : "sec"}" data-a="status" data-id="${x.id_vaga}" data-ativa="${x.ativa ? 0 : 1}">${x.ativa ? "Desativar" : "Ativar"}</button></td></tr>`;
  }).join("") : linhasVazias(7);
}

$("lista").onclick = async e => {
  const b = e.target.closest("button"); if (!b) return;
  const id = b.dataset.id; let r;
  if (b.dataset.a === "vincular") {
    const cli = $("sel" + id).value; if (!cli) return aviso("Escolha um cliente mensalista.", "erro");
    r = await acao(() => api(`/vagas/${id}/vincular`, { metodo: "POST", corpo: { id_cliente: Number(cli) } }), x => x.mensagem);
  } else if (b.dataset.a === "desvincular") {
    r = await acao(() => api(`/vagas/${id}/desvincular`, { metodo: "POST" }), "Vaga desvinculada.");
  } else {
    r = await acao(() => api(`/vagas/${id}/status`, { metodo: "PATCH", corpo: { ativa: b.dataset.ativa === "1" } }), x => x.mensagem);
  }
  if (r) carregar();
};
$("form").onsubmit = async e => {
  e.preventDefault();
  if (await acao(() => api("/vagas", { metodo: "POST", corpo: formParaObjeto(e.target) }), "Vaga cadastrada.")) { e.target.reset(); carregar(); }
};
(async () => { await iniciarPagina("vagas"); carregar(); })();
