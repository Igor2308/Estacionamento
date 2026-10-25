const $ = id => document.getElementById(id);
let paginador;
function hoje() { return new Date().toLocaleDateString("sv-SE"); } // AAAA-MM-DD no relógio local

const validarValor = v => (!dinheiroValido(v) ? "Valor inválido. Use números, com vírgula e até 2 casas (ex.: 5,00)." : null);
const seq = formularioSequencial({
  form: $("form"), botao: $("salvar"),
  campos: [
    { el: $("tipo_veiculo"), erroVazio: "Selecione o tipo de veículo." },
    { el: $("valor_periodo_30_min"), filtro: filtros.dinheiro, validar: validarValor },
    { el: $("mensalidade_por_vaga"), filtro: filtros.dinheiro, validar: validarValor },
    { el: $("inicio"), erroVazio: "Informe a data de início da vigência.",
      validar: v => (/^\d{4}-\d{2}-\d{2}$/.test(v) && !isNaN(new Date(v)) && v >= "2000-01-01" && v <= "2100-12-31" ? null : "Data inválida.") },
  ],
});

paginador = criarPaginador({
  barra: $("paginacao"),
  carregar: pagina => acao(() => api(`/tarifas?pagina=${pagina}`)),
  desenhar: (dados, { vazio }) => {
    $("lista").innerHTML = dados.length ? dados.map(t => `<tr>
      <td><b>${TIPOS_VEICULO[t.tipo_veiculo] || esc(t.tipo_veiculo)}</b></td><td>${dataSimples(t.vigencia_inicio)}</td><td>${t.vigencia_fim ? dataSimples(t.vigencia_fim) : "em aberto"}</td>
      <td>${moeda(t.valor_periodo_30_min)}</td><td>${moeda(t.mensalidade_por_vaga)}</td>
      <td>${Number(t.vigente) ? '<span class="tag ok">Vigente</span>' : '<span class="tag off">Encerrada / futura</span>'}</td>
      <td>${celulaCadastro(t)}</td></tr>`).join("")
      : linhasVazias(7, "Nenhuma tarifa cadastrada — cadastre uma acima.");
  },
});

$("form").onsubmit = async e => {
  e.preventDefault();
  if (!seq.tocarTudo()) return;
  const d = formParaObjeto(e.target);
  d.tipo_veiculo = $("tipo_veiculo").value;
  d.valor_periodo_30_min = $("valor_periodo_30_min").value.replace(",", ".");
  d.mensalidade_por_vaga = $("mensalidade_por_vaga").value.replace(",", ".");
  d.vigencia_inicio = $("inicio").value;
  if (await acao(() => api("/tarifas", { metodo: "POST", corpo: d }), "Tarifa cadastrada.")) { e.target.reset(); $("inicio").value = hoje(); seq.limpar(); paginador.recarregar(); }
};
(async () => { await iniciarPagina("tarifas"); $("inicio").value = hoje(); seq.limpar(); paginador.ir(1); })();
