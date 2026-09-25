"""Leitura local de NF-e e apresentação dos dados no formato do portal."""
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from html import escape
import xml.etree.ElementTree as ET


def text(node, path="."):
    found = node.find(path) if node is not None else None
    return (found.text or "").strip() if found is not None else ""


def number(value, places=None):
    if not value:
        return ""
    try:
        amount = Decimal(value)
        if not amount.is_finite():
            return value
        places = max(0, -amount.as_tuple().exponent) if places is None else places
        return f"{amount:,.{min(places, 10)}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    except InvalidOperation:
        return value


def date(value):
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if "T" not in value and " " not in value:
            return parsed.strftime("%d/%m/%Y")
        offset = parsed.strftime("%z")
        return parsed.strftime("%d/%m/%Y %H:%M:%S") + (f"{offset[:3]}:{offset[3:]}" if offset else "")
    except ValueError:
        return value


def document(value):
    if len(value) == 14:
        return f"{value[:2]}.{value[2:5]}.{value[5:8]}/{value[8:12]}-{value[12:]}"
    if len(value) == 11:
        return f"{value[:3]}.{value[3:6]}.{value[6:9]}-{value[9:]}"
    return value


def phone(value):
    if value.isdigit() and len(value) in (10, 11):
        return f"({value[:2]}) {value[2:-4]}-{value[-4:]}"
    return value


def coded(value, options):
    return f"{value} - {options[value]}" if value in options else value


MAPS = {
    "tpNF": {"0": "Entrada", "1": "Saída"},
    "idDest": {"1": "Operação Interna", "2": "Operação Interestadual", "3": "Operação com Exterior"},
    "indFinal": {"0": "Não", "1": "Sim"},
    "indPres": {"0": "Não se aplica", "1": "Operação presencial", "2": "Operação não presencial, pela Internet", "3": "Operação não presencial, teleatendimento", "4": "NFC-e em operação com entrega a domicílio", "5": "Operação presencial, fora do estabelecimento", "9": "Operação não presencial, outros"},
    "procEmi": {"0": "com aplicativo do Contribuinte", "1": "Avulsa pelo Fisco", "2": "Avulsa pelo Contribuinte", "3": "Aplicativo fornecido pelo Fisco"},
    "tpEmis": {"1": "Normal"},
    "finNFe": {"1": "Normal", "2": "Complementar", "3": "Ajuste", "4": "Devolução de mercadoria"},
    "indIntermed": {"0": "Operação sem intermediador", "1": "Operação em site ou plataforma de terceiros"},
    "CRT": {"1": "Simples Nacional", "2": "Simples Nacional - excesso de sublimite de receita bruta", "3": "Regime Normal", "4": "Simples Nacional - Microempreendedor Individual (MEI)"},
    "indIEDest": {"1": "Contribuinte ICMS (informar a IE do destinatário)", "2": "Contribuinte isento de Inscrição Estadual", "9": "Não Contribuinte"},
    "modFrete": {"0": "Contratação do Frete por conta do Remetente (CIF)", "1": "Contratação do Frete por conta do Destinatário (FOB)", "2": "Contratação do Frete por conta de Terceiros", "3": "Transporte Próprio por conta do Remetente", "4": "Transporte Próprio por conta do Destinatário", "9": "Sem Ocorrência de Transporte"},
    "indPag": {"0": "Pagamento à vista", "1": "Pagamento a prazo"},
    "tPag": {"01": "Dinheiro", "02": "Cheque", "03": "Cartão de Crédito", "04": "Cartão de Débito", "05": "Crédito Loja", "10": "Vale Alimentação", "11": "Vale Refeição", "12": "Vale Presente", "13": "Vale Combustível", "15": "Boleto Bancário", "16": "Depósito Bancário", "17": "Pagamento Instantâneo (PIX)", "18": "Transferência bancária / Carteira Digital", "19": "Programa de fidelidade, Cashback, Crédito Virtual", "90": "Sem pagamento", "99": "Outros"},
    "tpImp": {"0": "Sem geração de DANFE", "1": "DANFE normal, retrato", "2": "DANFE normal, paisagem", "3": "DANFE Simplificado", "4": "DANFE NFC-e", "5": "DANFE NFC-e em mensagem eletrônica"},
    "indTot": {"0": "O valor do item não compõe o valor total da NF-e", "1": "O valor do item (vProd) compõe o valor total da NF-e (vProd)"},
}


class Invoice:
    def __init__(self, data):
        self.root = ET.fromstring(data)
        for node in self.root.iter():
            node.tag = node.tag.rsplit("}", 1)[-1]
        notes = list(self.root.iter("infNFe"))
        if len(notes) != 1 or notes[0].find("ide") is None:
            raise ValueError("Selecione um XML contendo uma única NF-e (NFe ou nfeProc). Arquivos de eventos e outros documentos não contêm os dados completos da nota.")
        self.info = notes[0]
        self.ide = self.info.find("ide")
        identifier = self.info.get("Id", "")
        self.key = identifier[3:] if identifier.startswith("NFe") else identifier
        self.protocol = next((p for p in self.root.iter("infProt") if not self.key or text(p, "chNFe") == self.key), None)
        if not self.key:
            self.key = text(self.protocol, "chNFe")


def field(label, value="", span=1):
    style = f' style="--span:{span}"' if span > 1 else ""
    safe_value = escape(str(value)).replace("\r\n", "\n").replace("\n", "<br>")
    return f'<div class="field"{style}><div class="label">{escape(str(label))}</div><div class="value">{safe_value}</div></div>'


def grid(fields, columns=3, extra=""):
    return f'<div class="field-grid {extra}" style="--cols:{columns}">' + "".join(field(*f) for f in fields) + "</div>"


def section(title, content):
    return f"<h3>{escape(title)}</h3>{content}"


def panel(title, content):
    return f'<div class="portal"><h2>{escape(title)}</h2>{content}</div>'


def empty(message="Nenhuma informação deste grupo foi informada no XML."):
    return f'<div class="empty">{escape(message)}</div>'


def table(headers, rows):
    if not rows:
        return empty()
    return '<div class="table-wrap"><table><thead><tr>' + "".join(f"<th>{escape(h)}</th>" for h in headers) + '</tr></thead><tbody>' + "".join('<tr>' + "".join(f'<td>{escape(str(v))}</td>' for v in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def value(node, path, fmt=None):
    raw = text(node, path)
    tag = path.split("/")[-1]
    if fmt == "doc":
        return document(raw)
    if fmt == "date":
        return date(raw)
    if isinstance(fmt, int):
        return number(raw, fmt)
    return coded(raw, MAPS.get(tag, {}))


def fields(node, specs, columns=3):
    return grid([(label, value(node, path, fmt[0] if fmt else None)) for path, label, *fmt in specs], columns)


def general(inv):
    key = inv.key
    if len(key) == 44:
        key = " ".join(key[a:b] for a, b in [(0, 2), (2, 6), (6, 20), (20, 22), (22, 25), (25, 34), (34, 43), (43, 44)])
    return panel("Dados Gerais", grid([("Chave de Acesso", key), ("Número", text(inv.ide, "nNF")), ("Versão XML", inv.info.get("versao", ""))], extra="general-grid"))


# Campos opcionais desconhecidos mantêm a tag original e a hierarquia do XML.
LABELS = {
    "ICMS": "ICMS Normal e ST", "IPI": "Imposto Sobre Produtos Industrializados", "PIS": "PIS", "COFINS": "COFINS", "II": "Imposto de Importação", "ISSQN": "ISSQN", "IBSCBS": "IBS / CBS", "IS": "Imposto Seletivo", "gIBSCBS": "Base e valores do IBS / CBS", "gIBSUF": "IBS Estadual", "gIBSMun": "IBS Municipal", "gCBS": "CBS", "IBSCBSTot": "Totais do IBS / CBS", "ISTot": "Totais do Imposto Seletivo", "ISSQNtot": "Totais do ISSQN", "retTrib": "Retenções de Tributos", "ICMSTot": "ICMS", "gIBS": "IBS", "gDif": "Diferimento", "gDevTrib": "Devolução de Tributos", "gRed": "Redução de Alíquota", "ICMSUFDest": "ICMS para a UF de Destino", "PISST": "PIS Substituição Tributária", "COFINSST": "COFINS Substituição Tributária",
    "orig": "Origem da Mercadoria", "CST": "CST", "CSOSN": "Código de Situação da Operação no Simples Nacional", "modBC": "Modalidade de Definição da Base de Cálculo", "vBC": "Base de Cálculo", "pICMS": "Alíquota do ICMS", "vICMS": "Valor do ICMS", "vICMSDeson": "Valor do ICMS Desonerado", "motDesICMS": "Motivo da Desoneração do ICMS", "pRedBC": "Percentual de Redução da Base de Cálculo", "modBCST": "Modalidade da Base de Cálculo do ICMS ST", "pMVAST": "Margem de Valor Adicionado do ICMS ST", "pRedBCST": "Redução da Base de Cálculo do ICMS ST", "vBCST": "Base de Cálculo ICMS ST", "pICMSST": "Alíquota do ICMS ST", "vICMSST": "Valor do ICMS ST", "vBCSTRet": "Base de Cálculo do ICMS ST Retido", "vICMSSTRet": "ICMS ST Retido", "pCredSN": "Alíquota de Crédito do Simples Nacional", "vCredICMSSN": "Crédito do ICMS do Simples Nacional", "vBCFCP": "Base de Cálculo do FCP", "pFCP": "Percentual do Fundo de Combate à Pobreza (FCP)", "vFCP": "Valor do Fundo de Combate à Pobreza (FCP)", "vFCPST": "Valor do FCP Retido por ST", "vFCPSTRet": "Valor do FCP Retido Anteriormente por ST", "pFCPST": "Alíquota do FCP ST", "vBCFCPST": "Base de Cálculo do FCP ST",
    "cEnq": "Código de Enquadramento", "clEnq": "Classe de Enquadramento", "cSelo": "Código do Selo", "qSelo": "Quantidade de Selos", "CNPJProd": "CNPJ do Produtor", "qUnid": "Quantidade Total na Unidade Padrão", "vUnid": "Valor por Unidade", "vIPI": "Valor do IPI", "pIPI": "Alíquota do IPI", "vPIS": "Valor do PIS", "pPIS": "Alíquota do PIS", "vCOFINS": "Valor da COFINS", "pCOFINS": "Alíquota da COFINS", "qBCProd": "Quantidade da Base de Cálculo", "vAliqProd": "Alíquota por Unidade", "vTotTrib": "Valor Aproximado dos Tributos", "cClassTrib": "Classificação Tributária (cClassTrib)", "indDoacao": "Operação de Doação", "pIBSUF": "Alíquota do IBS da UF", "vIBSUF": "Valor do IBS da UF", "pIBSMun": "Alíquota do IBS do Município", "vIBSMun": "Valor do IBS Municipal", "vIBS": "Valor do IBS", "pCBS": "Alíquota da CBS", "vCBS": "Valor da CBS", "vBCIBSCBS": "Base de Cálculo do IBS / CBS", "pDif": "Percentual de Diferimento", "vDif": "Valor do Diferimento", "pRedAliq": "Percentual de Redução de Alíquota", "pAliqEfet": "Alíquota Efetiva", "vDevTrib": "Valor da Devolução de Tributos",
    "transporta": "Transportadora", "retTransp": "Retenção do ICMS do Transporte", "veicTransp": "Veículo de Transporte", "reboque": "Reboque", "vol": "Volumes", "lacres": "Lacres", "nLacre": "Número do Lacre", "qVol": "Quantidade de Volumes", "esp": "Espécie", "marca": "Marca", "nVol": "Numeração", "pesoL": "Peso Líquido", "pesoB": "Peso Bruto", "placa": "Placa", "RNTC": "Registro Nacional de Transportadores de Carga", "vServ": "Valor do Serviço", "vBCRet": "Base de Cálculo da Retenção", "pICMSRet": "Alíquota da Retenção", "vICMSRet": "Valor do ICMS Retido", "CFOP": "CFOP", "cMunFG": "Município da Ocorrência do Fato Gerador", "balsa": "Balsa", "vagao": "Vagão",
    "CNPJ": "CNPJ", "CPF": "CPF", "xNome": "Nome / Razão Social", "IE": "Inscrição Estadual", "xEnder": "Endereço", "xMun": "Município", "UF": "UF", "card": "Dados do Cartão", "tpIntegra": "Tipo de Integração", "tBand": "Bandeira da Operadora", "cAut": "Número de Autorização", "CNPJReceb": "CNPJ do Recebedor", "idTermPag": "Identificador do Terminal", "vTroco": "Valor do Troco", "dPag": "Data do Pagamento", "CNPJPag": "CNPJ do Estabelecimento do Pagamento", "UFPag": "UF do Estabelecimento do Pagamento",
    "obsCont": "Observação do Contribuinte", "obsFisco": "Observação do Fisco", "xTexto": "Descrição", "procRef": "Processo Referenciado", "nProc": "Número do Processo", "indProc": "Origem do Processo", "tpAto": "Tipo de Ato", "NFref": "Documento Fiscal Referenciado", "refNFe": "Chave da NF-e Referenciada", "refCTe": "Chave do CT-e Referenciado", "autXML": "Autorizados a Acessar o XML", "infRespTec": "Responsável Técnico", "xContato": "Contato", "email": "E-mail", "fone": "Telefone", "entrega": "Local de Entrega", "retirada": "Local de Retirada", "compra": "Dados da Compra", "xNEmp": "Nota de Empenho", "xPed": "Pedido", "xCont": "Contrato", "exporta": "Exportação", "cana": "Cana-de-açúcar", "infIntermed": "Intermediador da Transação", "idCadIntTran": "Identificação no Intermediador", "infAdProd": "Informações Adicionais do Produto", "impostoDevol": "Imposto Devolvido", "DI": "Declaração de Importação", "detExport": "Detalhes de Exportação", "rastro": "Rastreabilidade", "med": "Medicamentos", "comb": "Combustíveis", "veicProd": "Veículo Novo", "arma": "Armamento", "RECOPI": "Registro de Controle de Papel Imune", "nItem": "Número do Item", "chNFe": "Chave de Acesso da NF-e", "DFeReferenciado": "Referenciamento de Item de Outros DF-e", "chaveAcesso": "Chave de Acesso do DF-e Referenciado",
}


def automatic_value(tag, raw):
    if tag in MAPS:
        return coded(raw, MAPS[tag])
    if "CNPJ" in tag or tag == "CPF":
        return document(raw)
    if tag == "fone":
        return phone(raw)
    if tag.startswith("dh") or tag in {"dPag", "dVenc", "dEmi", "dFab", "dVal"}:
        return date(raw)
    if tag.startswith(("v", "p", "q")) and raw:
        try:
            Decimal(raw)
            return number(raw)
        except InvalidOperation:
            pass
    return raw


def generic(node, title=None):
    if node is None:
        return ""
    # As variantes são escolhas do esquema; o CST/CSOSN identifica a tributação.
    if node.tag in {"ICMS", "PIS", "COFINS"} and len(node) == 1 and len(node[0]):
        return generic(node[0], title or LABELS.get(node.tag, node.tag))
    direct = [(LABELS.get(k, k), v) for k, v in node.attrib.items()]
    if not len(node):
        direct.append((LABELS.get(node.tag, node.tag), automatic_value(node.tag, (node.text or "").strip())))
    direct.extend((LABELS.get(c.tag, c.tag), automatic_value(c.tag, (c.text or "").strip())) for c in node if not len(c))
    content = grid(direct) if direct else ""
    counts = Counter(c.tag for c in node if len(c))
    seen = Counter()
    for child in node:
        if len(child):
            seen[child.tag] += 1
            name = LABELS.get(child.tag, child.tag)
            if counts[child.tag] > 1:
                name += f" {seen[child.tag]}"
            content += f'<div class="subgroup">{generic(child, name)}</div>'
    return section(title or LABELS.get(node.tag, node.tag), content)


def extras(node, used):
    if node is None:
        return ""
    remainder = ET.Element(node.tag)
    remainder.extend(c for c in node if c.tag not in used)
    return generic(remainder, "Outros dados informados no XML") if len(remainder) else ""


def party_summary(inv, name):
    party = inv.info.find(name)
    address = f"ender{'Emit' if name == 'emit' else 'Dest'}"
    idtag = "CPF" if text(party, "CPF") else "CNPJ"
    return grid([(idtag, document(text(party, idtag))), ("Nome / Razão Social", text(party, "xNome")), ("Inscrição Estadual", text(party, "IE")), ("UF", text(party, f"{address}/UF"))], 4, "party-grid")


def nfe(inv):
    ide = inv.ide
    content = grid([("Modelo", text(ide, "mod")), ("Série", text(ide, "serie")), ("Número", text(ide, "nNF")), ("Data de Emissão", date(text(ide, "dhEmi") or text(ide, "dEmi"))), ("Data Saída/Entrada", date(text(ide, "dhSaiEnt") or text(ide, "dSaiEnt"))), ("Valor Total da Nota Fiscal", number(text(inv.info, "total/ICMSTot/vNF"), 3))], 6, "identification-grid")
    content += section("Emitente", party_summary(inv, "emit"))
    content += section("Destinatário", party_summary(inv, "dest") + fields(ide, [("idDest", "Destino da operação"), ("indFinal", "Consumidor final"), ("indPres", "Presença do Comprador")]))
    specs = [("procEmi", "Processo"), ("verProc", "Versão do Processo"), ("tpEmis", "Tipo de Emissão"), ("finNFe", "Finalidade"), ("tpNFDebito", "Tipo de Nota de Débito"), ("tpNFCredito", "Tipo de Nota de Crédito"), ("natOp", "Natureza da Operação"), ("indIntermed", "Indicador de Intermediador / Marketplace"), ("tpNF", "Tipo da Operação"), ("dPrevEntrega", "Data da Previsão de Entrega", "date"), ("cMunFG", "Município de Ocorrência do Fato Gerador"), ("cMunFGIBS", "Município de Ocorrência do Fato Gerador do IBS / CBS")]
    content += section("Emissão", fields(ide, specs, 4) + grid([("Digest Value da NF-e", text(inv.protocol, "digVal") or text(inv.root, ".//Signature/SignedInfo/Reference/DigestValue"))], 1))
    content += section("Compra Governamental", fields(ide, [("gCompraGov/tpEnteGov", "Tipo de ente governamental"), ("gCompraGov/pRedutor", "Percentual de redução de alíquota"), ("gCompraGov/tpOperGov", "Tipo de operação com o ente governamental")]))
    protocol = inv.protocol
    status = "Situação no XML: " + (text(protocol, "xMotivo") or text(protocol, "cStat") or "Protocolo de autorização não informado")
    environment = text(protocol, "tpAmb") or text(ide, "tpAmb")
    if environment:
        status += " (Ambiente: " + {"1": "produção", "2": "homologação"}.get(environment, environment) + ")"
    rows = []
    if protocol is not None:
        rows.append([text(protocol, "xMotivo"), text(protocol, "nProt"), date(text(protocol, "dhRecbto")), ""])
    for event in inv.root.iter("procEventoNFe"):
        details = event.find("evento/infEvento")
        response = event.find("retEvento/infEvento")
        if text(details, "chNFe") != inv.key:
            continue
        rows.append([text(details, "detEvento/descEvento") or text(details, "tpEvento"), text(response, "nProt"), date(text(response, "dhRegEvento")), ""])
    content += section(status, table(["Eventos da NF-e", "Protocolo", "Data de Autorização / Registro", "Data Inclusão AN"], rows))
    used = {s[0] for s in specs} | {"mod", "serie", "nNF", "dhEmi", "dhSaiEnt", "idDest", "indFinal", "indPres", "tpAmb", "tpImp", "gCompraGov"}
    content += extras(ide, used)
    return panel(f"Dados da NF-e: {inv.key}", content)


def party(inv, name):
    node = inv.info.find(name)
    is_emit = name == "emit"
    address_tag = "enderEmit" if is_emit else "enderDest"
    address = node.find(address_tag) if node is not None else None
    identifier = "CPF" if text(node, "CPF") else "CNPJ"
    addr = ", ".join(filter(None, [text(address, "xLgr"), text(address, "nro"), text(address, "xCpl")]))
    cep = text(address, "CEP")
    cep = f"{cep[:5]}-{cep[5:]}" if len(cep) == 8 else cep
    data = [("Nome / Razão Social", text(node, "xNome"), 1 if is_emit else 2)]
    if is_emit:
        data.append(("Nome Fantasia", text(node, "xFant")))
    data += [(identifier, document(text(node, identifier))), ("Endereço", addr), ("Bairro / Distrito", text(address, "xBairro")), ("CEP", cep), ("Município", " - ".join(filter(None, [text(address, "cMun"), text(address, "xMun")]))), ("Telefone", phone(text(address, "fone"))), ("UF", text(address, "UF")), ("País", " - ".join(filter(None, [text(address, "cPais"), text(address, "xPais")])))]
    if is_emit:
        data += [("Inscrição Estadual", text(node, "IE")), ("Inscrição Estadual do Substituto Tributário", text(node, "IEST")), ("Inscrição Municipal", text(node, "IM")), ("Município da Ocorrência do Fato Gerador do ICMS", text(inv.ide, "cMunFG")), ("CNAE Fiscal", text(node, "CNAE")), ("Código de Regime Tributário", value(node, "CRT"))]
    else:
        data += [("Indicador IE", value(node, "indIEDest")), ("Inscrição Estadual", text(node, "IE")), ("Inscrição SUFRAMA", text(node, "ISUF")), ("IM", text(node, "IM")), ("E-mail", text(node, "email"))]
    content = grid(data, 2)
    content += extras(node, {"xNome", "xFant", "CNPJ", "CPF", address_tag, "IE", "IEST", "IM", "CNAE", "CRT", "indIEDest", "ISUF", "email"})
    content += extras(address, {"xLgr", "nro", "xCpl", "xBairro", "CEP", "cMun", "xMun", "fone", "UF", "cPais", "xPais"})
    if not is_emit:
        for tag in ("retirada", "entrega"):
            content += generic(inv.info.find(tag))
    return panel("Dados do Emitente" if is_emit else "Dados do Destinatário", content)


PRODUCT_SPECS = [
    ("cProd", "Código do Produto"), ("NCM", "Código NCM"), ("CEST", "Código CEST"), ("indEscala", "Indicador de Escala Relevante"), ("CNPJFab", "CNPJ do Fabricante da Mercadoria", "doc"), ("cBenef", "Código de Benefício Fiscal na UF"), ("EXTIPI", "Código EX da TIPI"), ("CFOP", "CFOP"), ("vOutro", "Outras Despesas Acessórias", 3), ("vDesc", "Valor do Desconto", 3), ("vFrete", "Valor Total do Frete", 3), ("vSeg", "Valor do Seguro", 3),
    ("indTot", "Indicador de Composição do Valor Total da NF-e"), ("cEAN", "Código EAN Comercial"), ("uCom", "Unidade Comercial"), ("qCom", "Quantidade Comercial", 4), ("cEANTrib", "Código EAN Tributável"), ("uTrib", "Unidade Tributável"), ("qTrib", "Quantidade Tributável", 4), ("vUnCom", "Valor unitário de comercialização", 10), ("vUnTrib", "Valor unitário de tributação", 10), ("xPed", "Número do pedido de compra"), ("nItemPed", "Item do pedido de compra"), ("nFCI", "Número da FCI")
]


def products(inv):
    content = '<div class="product-head"><span>Num.</span><span>Descrição</span><span>Qtd.</span><span>Unidade Comercial</span><span>Valor (R$)</span></div>'
    items = inv.info.findall("det")
    for index, item in enumerate(items, 1):
        prod = item.find("prod")
        summary = [item.get("nItem", str(index)), text(prod, "xProd"), number(text(prod, "qCom"), 4), text(prod, "uCom"), number(text(prod, "vProd"), 3)]
        details = fields(prod, PRODUCT_SPECS[:12])
        details += fields(prod, PRODUCT_SPECS[12:13], 1) + fields(prod, PRODUCT_SPECS[13:])
        details += grid([("Valor Aproximado dos Tributos", number(text(item, "imposto/vTotTrib"), 3))])
        details += extras(prod, {s[0] for s in PRODUCT_SPECS} | {"xProd", "vProd"})
        tax = item.find("imposto")
        if tax is not None:
            for group in tax:
                if group.tag != "vTotTrib":
                    details += generic(group)
        details += section("Informações adicionais do produto", grid([("Descrição", text(item, "infAdProd"))], 1))
        details += extras(item, {"prod", "imposto", "infAdProd"})
        opened = " open" if index == 1 else ""
        content += f'<details class="product"{opened}><summary><span class="product-summary">' + "".join(f'<span>{escape(v)}</span>' for v in summary) + f'</span></summary><div class="product-body">{details}</div></details>'
    return panel("Dados dos Produtos e Serviços", content if items else empty("Nenhum produto informado no XML."))


TOTAL_SPECS = [
    ("vBC", "Base de Cálculo ICMS", 2), ("vICMS", "Valor do ICMS", 3), ("vICMSDeson", "Valor do ICMS Desonerado", 3), ("vFCP", "Valor Total do FCP", 3), ("vFCPUFDest", "Valor Total ICMS FCP", 3), ("vICMSUFDest", "Valor Total ICMS Interestadual UF Destino", 3), ("vICMSUFRemet", "Valor Total ICMS Interestadual UF Rem.", 3), ("vBCST", "Base de Cálculo ICMS ST", 2), ("vST", "Valor ICMS Substituição", 3), ("vFCPST", "Valor Total do FCP retido por ST", 3), ("vFCPSTRet", "Valor Total do FCP retido anteriormente por ST", 3),
    ("qBCMono", "Quantidade tributada do ICMS monofásico próprio", 4), ("vICMSMono", "Valor do ICMS monofásico próprio", 3), ("qBCMonoReten", "Quantidade tributada do ICMS monofásico sujeito a retenção", 4), ("vICMSMonoReten", "Valor do ICMS monofásico sujeito a retenção", 3), ("qBCMonoRet", "Quantidade tributada do ICMS monofásico retido anteriormente", 4), ("vICMSMonoRet", "Valor do ICMS monofásico retido anteriormente", 3),
    ("vProd", "Valor Total dos Produtos", 3), ("vFrete", "Valor do Frete", 3), ("vSeg", "Valor do Seguro", 3), ("vDesc", "Valor Total dos Descontos", 3), ("vII", "Valor Total do II", 3), ("vIPI", "Valor Total do IPI", 3), ("vIPIDevol", "Valor Total do IPI Devolvido", 3), ("vPIS", "Valor do PIS", 3), ("vCOFINS", "Valor da COFINS", 3), ("vOutro", "Outras Despesas Acessórias", 3), ("vNF", "Valor Total da NF-e", 3), ("vTotTrib", "Valor Aproximado dos Tributos", 3)
]


def totals(inv):
    node = inv.info.find("total/ICMSTot")
    content = section("ICMS", fields(node, TOTAL_SPECS[:11], 4) + fields(node, TOTAL_SPECS[11:17], 2) + fields(node, TOTAL_SPECS[17:], 4))
    content += extras(node, {s[0] for s in TOTAL_SPECS})
    total = inv.info.find("total")
    if total is not None:
        content += "".join(generic(group) for group in total if group.tag != "ICMSTot")
    return panel("Totais", content)


def transport(inv):
    node = inv.info.find("transp")
    content = fields(node, [("modFrete", "Modalidade do Frete")], 1)
    if node is not None:
        counts = Counter(c.tag for c in node)
        seen = Counter()
        for group in node:
            if group.tag == "modFrete":
                continue
            seen[group.tag] += 1
            title = LABELS.get(group.tag, group.tag)
            if counts[group.tag] > 1:
                title += f" {seen[group.tag]}"
            content += generic(group, title)
    return panel("Dados do Transporte", content)


def billing(inv):
    node = inv.info.find("cobr")
    content = section("Fatura", fields(node, [("fat/nFat", "Número"), ("fat/vOrig", "Valor Original", 3), ("fat/vDesc", "Valor do Desconto", 3), ("fat/vLiq", "Valor Líquido", 3)]))
    installments = node.findall("dup") if node is not None else []
    content += section("Duplicatas", table(["Número", "Vencimento", "Valor"], [[text(d, "nDup"), date(text(d, "dVenc")), number(text(d, "vDup"), 3)] for d in installments]))
    payments = inv.info.findall("pag/detPag")
    rows = [[value(p, "indPag"), value(p, "tPag"), text(p, "xPag"), number(text(p, "vPag"), 3)] for p in payments]
    content += section("Formas de Pagamento", table(["Ind. Forma de Pagamento", "Meio de Pagamento", "Descrição do Meio de Pagamento", "Valor (R$)"], rows))
    for index, payment in enumerate(payments, 1):
        more = extras(payment, {"indPag", "tPag", "xPag", "vPag"})
        if more:
            content += section(f"Detalhes do Pagamento {index}", more)
    content += extras(inv.info.find("pag"), {"detPag"})
    content += extras(node, {"fat", "dup"})
    content += extras(node.find("fat") if node is not None else None, {"nFat", "vOrig", "vDesc", "vLiq"})
    return panel("Dados de Cobrança", content)


def additional(inv):
    node = inv.info.find("infAdic")
    content = fields(inv.ide, [("tpImp", "Formato de Impressão DANFE")], 1)
    content += section("Informações Adicionais de Interesse do Fisco", grid([("Descrição", text(node, "infAdFisco"))], 1))
    content += section("Informações Complementares de Interesse do Contribuinte", grid([("Descrição", text(node, "infCpl"))], 1))
    content += extras(node, {"infAdFisco", "infCpl"})
    content += extras(inv.info, {"ide", "emit", "dest", "det", "total", "transp", "cobr", "pag", "infAdic", "retirada", "entrega"})
    return panel("Informações Adicionais", content)


def render_tabs(inv):
    return [("NFe", nfe(inv)), ("Emitente", party(inv, "emit")), ("Destinatário", party(inv, "dest")), ("Produtos e Serviços", products(inv)), ("Totais", totals(inv)), ("Transporte", transport(inv)), ("Cobrança", billing(inv)), ("Informações Adicionais", additional(inv))]
