function toggleCategory(element) {

    const container = element.closest('.fitflix-category')

    document.querySelectorAll('.fitflix-category').forEach(cat => {
        cat.classList.remove('active')
    })

    container.classList.add('active')
}
document.addEventListener('DOMContentLoaded', function () {

    document.querySelectorAll('.fitflix-exercise-play').forEach(play => {

        play.addEventListener('click', function () {

            const card = this.closest('.fitflix-exercise-card')
            const thumb = card.querySelector('.fitflix-exercise-thumb')

            const variacoes = JSON.parse(card.getAttribute('data-variacoes'))

            console.log("Play clicado:", card.getAttribute('data-nome-exercicio'))

            if (variacoes.length > 0) {
                const gif = variacoes[0].gif

                console.log("GIF carregado:", gif)

                thumb.src = gif
            }
        })

    })

})