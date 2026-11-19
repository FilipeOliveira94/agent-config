---
name: issue-cycle
description: "Leva uma issue (ou fase) do plano aprovado até a entrega verificada, no time PO, dev, Reviewer e Filipe. Use quando citarem uma issue, um critério de aceite, uma feature a construir, ou pedirem para planejar, revisar, fechar ou verificar uma issue."
---

# Ciclo de issue

Uma issue ou fase por vez. O texto de aceite é a definição de pronto: não puxe issues futuras e não mude o aceite durante a construção. As regras de time estão na skill `fluxo-dev`; o `AGENTS.md` do repositório prevalece no que for específico do projeto.

## 1. Planejar (PO, só quando o Filipe pedir)

Leia a issue, o aceite e o status do projeto. Não altere arquivos.

Responda com escopo, fora de escopo, abordagem, riscos e o que uma pessoa consegue fazer quando estiver pronto. **Pare.** Só segue com o plano aprovado explicitamente pelo Filipe.

## 2. Construir (dev, só quando o Filipe mandar no chat do dev)

Branch da issue a partir da `main` atualizada, salvo exceção do repositório (`open-data-platform`: commits locais na `main`).

Faça a menor mudança que torna o comportamento aceito verdadeiro. Não acrescente confirmação, restrição ou passo que a issue não pediu. Ao extrair lógica repetida ou escolher fronteiras entre módulos, consulte a skill `code-structure`; a arquitetura existente do projeto prevalece.

A ordem de implementar já autoriza commitar, dar push da branch da issue, abrir o PR e ler o CI. Não autoriza merge, exclusão de branch, push na `main` nem CD.

## 3. Verificar (dev)

- Exercite cada comportamento da issue como a pessoa usuária o faria. Comportamento não exercitado não está pronto; diga qual ficou de fora e por quê.
- Um check interno verde não basta se a pessoa vê outra superfície. Olhe essa superfície.
- Check não executado não é aprovação. Mostre comando e saída.
- Analise o CI do PR (no `open-data-platform`, os checks locais) antes de entregar.

## 4. Registrar e entregar (dev)

Registre o que foi construído e o que os checks mostraram, sem desvios que não mudam o uso do resultado. Compare com o aceite: o que está cumprido e o que segue aberto.

Com o CI analisado, sinalize ao PO e ao Reviewer que está pronto para revisão, e avise o Filipe:
- o que fez; PR e head (no `open-data-platform`, o hash do último commit); CI e checks com saídas; pontos em aberto; a classificação da mudança (pequena ou grande, critério na fase 5; quem classifica é o dev).

## 5. Aprovar (PO + Reviewer)

- Revisam só depois do sinal do dev. PO julga contra o aceite e o escopo; Reviewer julga o diff e o CI. Os dois aprovam **a mesma versão** (mesmo hash).
- Qualquer objeção bloqueia. O dev corrige com novos commits, analisa o CI de novo e sinaliza de novo. Cada sinal é uma rodada.
- Duas rodadas de divergência: o Filipe decide.
- Mudança pequena (docs, texto, ajuste de config, bump patch de dependência, ou bugfix contido de até ~50 linhas em até 3 arquivos, sem tocar arquitetura, modelo de dados/schema, auth/segurança, infra/deploy, API pública ou lógica de pipeline; na dúvida, é grande): classificada pelo dev, basta o PO. O Reviewer não revisa, só faz o merge.

## 6. Publicar (Reviewer, só com o sim do Filipe)

Reviewer propõe o merge ao Filipe e executa só após o sim explícito; o mesmo vale para apagar a branch e rodar CD. O Filipe pode fazer ele mesmo ou ordenar que um bot específico faça. No `open-data-platform`, o push na `main` segue esta regra. Exceção: no `pedsletter`, PRs de conteúdo entram pelo merge automático. Depois, avise o PO.

## 7. Fechar (PO)

PO atualiza o backlog e propõe o próximo passo ao Filipe.
