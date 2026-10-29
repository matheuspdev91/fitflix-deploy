document.addEventListener("DOMContentLoaded", function () {

    console.log("🔥 Script carregado");

    function getPrincipal() {
        return document.getElementById("id_grupo_muscular");
    }

    function getVariacoes() {
        return document.querySelectorAll("select[id*='grupo_muscular']");
    }

    function copiarGrupo() {
        const principal = getPrincipal();
        const variacoes = getVariacoes();

        if (!principal) {
            console.log("❌ Principal não encontrado");
            return;
        }

        console.log("👉 Valor principal:", principal.value);
        console.log("👉 Total variações:", variacoes.length);

        variacoes.forEach((campo) => {
            if (campo !== principal) {
                campo.value = principal.value;

                // força atualização visual do Django
                campo.dispatchEvent(new Event("change", { bubbles: true }));
            }
        });

        console.log("✅ Sincronizado");
    }

    // 🔁 Quando mudar o select principal
    document.body.addEventListener("change", function (e) {
        if (e.target.id === "id_grupo_muscular") {
            setTimeout(copiarGrupo, 100);
        }
    });

    // ➕ Quando clicar em "Adicionar outra variação"
    document.body.addEventListener("click", function (e) {
        if (e.target.closest(".add-row a")) {
            console.log("➕ Nova variação detectada");
            setTimeout(copiarGrupo, 200);
        }
    });

});