import os
import shutil
import unicodedata
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "projeto.settings")

import django
django.setup()

from django.conf import settings
from core.models import VariacaoExercicio


SOURCE_ROOT = Path(settings.BASE_DIR) / "media" / "exercicios"
STAGING_ROOT = Path("/tmp/fitflix-pendentes")


def norm(text):
    text = str(text or "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().strip().split())


def find_candidates(filename):
    target = filename.lower()
    return [
        p for p in SOURCE_ROOT.rglob("*")
        if p.is_file() and p.name.lower() == target
    ]


def choose_candidate(candidates, grupo):
    if len(candidates) == 1:
        return candidates[0]

    grupo_norm = norm(grupo)

    scored = []

    for candidate in candidates:
        parts = [norm(p) for p in candidate.relative_to(SOURCE_ROOT).parts]

        score = 0

        # Match exato de algum diretório com o grupo muscular
        if grupo_norm and grupo_norm in parts:
            score += 100

        # Match parcial no caminho
        if grupo_norm:
            for part in parts:
                if grupo_norm in part or part in grupo_norm:
                    score += 50

        scored.append((score, candidate))

    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored:
        return None

    best_score = scored[0][0]

    # Se não há qualquer evidência para escolher entre duplicados,
    # não arrisca.
    if best_score == 0:
        return None

    best = [p for score, p in scored if score == best_score]

    if len(best) != 1:
        return None

    return best[0]


def main():
    pendentes = (
        VariacaoExercicio.objects
        .exclude(gif__isnull=True)
        .exclude(gif="")
        .exclude(gif__startswith="fitflix/")
        .select_related("grupo_muscular", "exercicio")
    )

    total = pendentes.count()

    print("=" * 60)
    print("STAGING DE MÍDIAS PENDENTES")
    print("=" * 60)
    print(f"Pendentes no banco: {total}")
    print(f"Origem:   {SOURCE_ROOT}")
    print(f"Destino:  {STAGING_ROOT}")
    print()

    if STAGING_ROOT.exists():
        shutil.rmtree(STAGING_ROOT)

    STAGING_ROOT.mkdir(parents=True, exist_ok=True)

    staged = 0
    missing = []
    ambiguous = []

    for v in pendentes:
        filename = Path(v.gif.name).name
        grupo = v.grupo_muscular.nome if v.grupo_muscular else ""

        candidates = find_candidates(filename)

        if not candidates:
            missing.append((v.id, v.exercicio.nome, v.nome, filename))
            continue

        source = choose_candidate(candidates, grupo)

        if source is None:
            ambiguous.append(
                (
                    v.id,
                    v.exercicio.nome,
                    v.nome,
                    filename,
                    [str(p.relative_to(SOURCE_ROOT)) for p in candidates],
                )
            )
            continue

        relative = source.relative_to(SOURCE_ROOT)
        destination = STAGING_ROOT / relative

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

        staged += 1

        print(
            f"[OK] V#{v.id} | {grupo or 'sem grupo'} | "
            f"{v.exercicio.nome} → {relative}"
        )

    print()
    print("=" * 60)
    print("RESULTADO")
    print("=" * 60)
    print(f"Pendentes:   {total}")
    print(f"Staged:      {staged}")
    print(f"Ausentes:    {len(missing)}")
    print(f"Ambíguos:    {len(ambiguous)}")

    if missing:
        print("\n=== AUSENTES ===")
        for item in missing:
            print(
                f"V#{item[0]} | {item[1]} | {item[2]} | {item[3]}"
            )

    if ambiguous:
        print("\n=== AMBÍGUOS ===")
        for item in ambiguous:
            print(f"V#{item[0]} | {item[1]} | {item[2]} | {item[3]}")
            for candidate in item[4]:
                print(f"    -> {candidate}")

    print()

    if staged == total and not missing and not ambiguous:
        print("✅ STAGING COMPLETO: 282/282 mídias preparadas.")
        print(f"Destino: {STAGING_ROOT}")
    else:
        print("⚠️ STAGING NÃO LIBERADO.")
        print("Resolva ausentes/ambíguos antes do upload.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
