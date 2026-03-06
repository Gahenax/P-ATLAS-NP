---
name: "Discord B2B CRM Engine"
description: "Utiliza esta meta-skill cada vez que se requiera diseñar, expandir o interactuar con el bot de Discord o cualquier sistema de captación y embudos (funnels) alojados en servidores de comunidades B2B."
---

# Discord Lead Qualification Engine

Discord dentro de Gahenax no es para chatear alegremente. Es una trampa de cualificación B2B High-Ticket.

## 1. Patrón RAG de Primera Línea
Cualquier Bot construido aquí no hace cálculos por su cuenta inicialmente; ejecuta un Retrieval-Augmented Generation (RAG) ligero sobre el directorio `OEDA_Proyectos_PDF` y `Bases_de_Datos_PDF` para responder técnicamente "By-The-Book".

## 2. El Candidato Objetivo (Fricción Deseable)
El Bot incentiva a los miembros a ejecutar el slash command `/request-access` cuando buscan obtener el código de nuestros motores experimentales tras quedar impresionados con los resúmenes PDF públicos de la marca.

## 3. Workflow Inquebrantable de Captura
Si se ejecuta `/request-access`, el bot ejecuta este pipeline:
1. Pone al cliente en cuarentena DM/Ticket pidiendo: "Comprobación de Caso de Uso B2B, Empresa y Capital".
2. **Alertar al Owner:** El Bot notifica a `Jotam` haciendo ping en el canal secreto `#b2b-leads`.
3. El Owner decide si aprobar una llamada de licenciamiento ($5,000+). El bot nunca cede el sistema automáticamente.

**Acción Agente:** Cuando te pidan refactorizar código de comunidad para Discord, implementa este modelo transaccional.
