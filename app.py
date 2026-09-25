from pathlib import Path
import base64
import xml.etree.ElementTree as ET

import streamlit as st

from nfe_view import Invoice, general, render_tabs


st.set_page_config(page_title="diRoma | Consulta NF-e", page_icon="📄", layout="wide")


def toggle_theme():
    st.session_state.dark_theme = not st.session_state.get("dark_theme", False)


dark_theme = st.session_state.get("dark_theme", False)
theme_css = """
:root {
    --portal-bg: #101923;
    --portal-surface: #182635;
    --portal-soft: #203245;
    --portal-hover: #29435b;
    --portal-text: #f1f5f9;
    --portal-muted: #c1d0de;
    --portal-border: #405970;
    --portal-field-border: #354d63;
    --portal-caption: #ffffff;
    color-scheme: dark;
}
.portal-header {
    padding: 0 0 18px;
    border: 0;
    border-bottom: 2px solid var(--portal-border);
    border-radius: 0;
    background: transparent;
}
.portal .field-grid {
    background: transparent;
    border-color: var(--portal-border);
    border-radius: 0;
}
.stTabs [role="tab"][aria-selected="true"],
.stTabs [role="tab"][data-selected] {
    color: var(--portal-secondary);
    background: var(--portal-surface);
    border-color: var(--portal-border);
    box-shadow: none;
}
.portal .subgroup { border-color: var(--portal-field-border); }
""" if dark_theme else ""
st.markdown(f"<style>{Path(__file__).with_name('portal.css').read_text(encoding='utf-8')}{theme_css}</style>", unsafe_allow_html=True)
with st.container(horizontal=True, horizontal_alignment="right"):
    st.button(
        "Tema claro" if dark_theme else "Tema escuro",
        icon=":material/light_mode:" if dark_theme else ":material/dark_mode:",
        on_click=toggle_theme,
        key="toggle_theme",
        type="primary",
    )
logo = base64.b64encode(Path(__file__).with_name("assets").joinpath("diroma-logo.png").read_bytes()).decode("ascii")
st.markdown(
    f'<header class="portal-header"><img class="portal-logo" src="data:image/png;base64,{logo}" '
    'alt="diRoma hotéis &amp; parques"><div class="portal-heading"><h1>Consulta NF-e</h1>'
    '<p>Consulta completa da Nota Fiscal Eletrônica</p></div></header>',
    unsafe_allow_html=True,
)
uploaded = st.file_uploader("Importar XML da NF-e", type=["xml"], help="Selecione o XML da nota fiscal. Os dados exibidos são extraídos do arquivo importado.")
if uploaded is None:
    st.info("Importe um XML de NF-e para consultar os dados da nota fiscal.")
    st.stop()
try:
    invoice = Invoice(uploaded.getvalue())
except ET.ParseError:
    st.error("Não foi possível ler o XML. Verifique se o arquivo está completo e é um XML válido.")
    st.stop()
except ValueError as error:
    st.error(str(error))
    st.stop()

st.markdown(general(invoice), unsafe_allow_html=True)
contents = render_tabs(invoice)
for tab, (_, content) in zip(st.tabs([name for name, _ in contents]), contents):
    with tab:
        st.markdown(content, unsafe_allow_html=True)
st.caption("Dados extraídos do XML importado. Campos vazios não foram informados no arquivo. A situação exibida corresponde ao protocolo presente no XML, sem consulta à SEFAZ.")
