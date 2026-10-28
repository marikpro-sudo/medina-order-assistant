{* Medina widget: one script tag. The token identifies the customer and delivery point. *}
<script src="{$medina_api|escape:'html':'UTF-8'}/medina.js"
        data-api="{$medina_api|escape:'html':'UTF-8'}"
        data-token="{$medina_token|escape:'html':'UTF-8'}"
        data-lang="{$medina_lang|escape:'html':'UTF-8'}"
        defer></script>
