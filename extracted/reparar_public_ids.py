import os
import django
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'projeto.settings')
django.setup()

from core.models import VariacaoExercicio
import cloudinary
import cloudinary.api
import cloudinary.uploader
from core.media_pipeline.cloudinary import CloudinaryConfig, CloudinaryUploader

def run():
    print('Iniciando reparo dos public_ids no Cloudinary...')
    config = CloudinaryConfig.from_env()
    uploader = CloudinaryUploader(config)
    
    variacoes = VariacaoExercicio.objects.filter(gif__startswith='fitflix/').exclude(gif__exact='')
    
    corrigidos = 0
    nao_encontrados = 0
    ja_corretos = 0
    erros = 0
    
    for v in variacoes:
        gif_name = v.gif.name
        
        if not gif_name.lower().endswith('.gif'):
            continue
            
        correct_public_id = str(Path(gif_name).with_suffix('')).replace('\\', '/')
        incorrect_public_id = gif_name # O que está no Cloudinary com .gif
        
        try:
            if uploader.exists(correct_public_id):
                ja_corretos += 1
                continue
        except Exception as e:
            pass
            
        try:
            if uploader.exists(incorrect_public_id):
                print(f'Renomeando: {incorrect_public_id} -> {correct_public_id}')
                cloudinary.uploader.rename(incorrect_public_id, correct_public_id)
                corrigidos += 1
            else:
                nao_encontrados += 1
        except Exception as exc:
            print(f'Erro ao tentar renomear {incorrect_public_id}: {exc}')
            erros += 1

    print('\n=========================================')
    print('RESULTADO DO REPARO:')
    print(f'Corrigidos (Renomeados): {corrigidos}')
    print(f'Já estavam corretos:     {ja_corretos}')
    print(f'Não encontrados (404):   {nao_encontrados}')
    print(f'Erros:                   {erros}')
    print('=========================================')

if __name__ == "__main__":
    run()
