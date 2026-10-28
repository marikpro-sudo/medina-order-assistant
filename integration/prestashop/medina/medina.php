<?php
/**
 * Medina order assistant — thin PrestaShop module (sketch).
 *
 * Injects the widget script on front-office pages for logged-in B2B customers and passes a
 * short-lived signed token instead of raw ids, so the backend can trust who is asking.
 */
if (!defined('_PS_VERSION_')) {
    exit;
}

class Medina extends Module
{
    public function __construct()
    {
        $this->name = 'medina';
        $this->tab = 'front_office_features';
        $this->version = '0.1.0';
        $this->author = 'Medina';
        $this->bootstrap = true;
        parent::__construct();
        $this->displayName = $this->l('Medina order assistant');
        $this->description = $this->l('Chat assistant that turns messy orders into order-upload files.');
    }

    public function install()
    {
        return parent::install()
            && $this->registerHook('displayBeforeBodyClosingTag')
            && Configuration::updateValue('MEDINA_API_URL', 'https://medina.example.com')
            && Configuration::updateValue('MEDINA_SECRET', bin2hex(random_bytes(32)));
    }

    public function uninstall()
    {
        Configuration::deleteByName('MEDINA_API_URL');
        Configuration::deleteByName('MEDINA_SECRET');
        return parent::uninstall();
    }

    public function hookDisplayBeforeBodyClosingTag($params)
    {
        $customer = $this->context->customer;
        if (!$customer || !$customer->isLogged()) {
            return '';
        }
        // The portal already stores the ERP customer number for each account; how it is stored
        // (custom field, group, or mapping table) is portal-specific.
        $erpCustomerId = $this->getErpCustomerId((int) $customer->id);
        if (!$erpCustomerId) {
            return '';
        }
        $deliveryPoint = (string) $this->context->cart->id_address_delivery;
        $token = $this->signToken($erpCustomerId, $deliveryPoint);

        $this->context->smarty->assign([
            'medina_api' => Configuration::get('MEDINA_API_URL'),
            'medina_token' => $token,
            'medina_lang' => $this->context->language->iso_code === 'kk' ? 'kk' : 'ru',
        ]);
        return $this->display(__FILE__, 'views/templates/hook/widget.tpl');
    }

    private function getErpCustomerId(int $idCustomer): ?string
    {
        // Sketch: replace with the portal's own lookup.
        $value = Db::getInstance()->getValue(
            'SELECT erp_customer_id FROM `' . _DB_PREFIX_ . 'medina_customer_map` WHERE id_customer = ' . $idCustomer
        );
        return $value ?: null;
    }

    /** payload.signature, where payload = base64url(json{c, p, exp}). Verified by the Medina backend. */
    private function signToken(string $customerId, string $deliveryPoint): string
    {
        $payload = rtrim(strtr(base64_encode(json_encode([
            'c' => $customerId,
            'p' => $deliveryPoint,
            'exp' => time() + 3600,
        ])), '+/', '-_'), '=');
        $sig = hash_hmac('sha256', $payload, Configuration::get('MEDINA_SECRET'));
        return $payload . '.' . $sig;
    }
}
