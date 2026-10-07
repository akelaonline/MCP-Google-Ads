<?php
/**
 * Plugin Name: MKT Measurement Bridge
 * Description: Controlled Measurement Ops abilities and GTM injection for WordPress.
 * Version: 0.1.0
 * Requires at least: 6.9
 * Requires PHP: 8.0
 * Author: MKT Marketing Digital
 * License: GPL-2.0-or-later
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

const MKT_MEASUREMENT_GTM_OPTION = 'mkt_measurement_gtm_container_id';
const MKT_MEASUREMENT_GTM_ENABLED_OPTION = 'mkt_measurement_gtm_enabled';

function mkt_measurement_valid_gtm_id( $value ) {
	return is_string( $value ) && 1 === preg_match( '/^GTM-[A-Z0-9]+$/i', trim( $value ) );
}

function mkt_measurement_container_id() {
	$value = (string) get_option( MKT_MEASUREMENT_GTM_OPTION, '' );
	return mkt_measurement_valid_gtm_id( $value ) ? strtoupper( trim( $value ) ) : '';
}

function mkt_measurement_enabled() {
	return (bool) get_option( MKT_MEASUREMENT_GTM_ENABLED_OPTION, false );
}

function mkt_measurement_register_category() {
	if ( ! function_exists( 'wp_register_ability_category' ) ) {
		return;
	}
	wp_register_ability_category(
		'mkt-measurement',
		array(
			'label'       => __( 'MKT Measurement', 'mkt-measurement' ),
			'description' => __( 'Controlled measurement and tagging operations.', 'mkt-measurement' ),
		)
	);
}
add_action( 'wp_abilities_api_categories_init', 'mkt_measurement_register_category' );

function mkt_measurement_get_config() {
	return array(
		'gtm_container_id' => mkt_measurement_container_id(),
		'gtm_enabled'      => mkt_measurement_enabled(),
		'wordpress'        => get_bloginfo( 'version' ),
		'home_url'         => home_url( '/' ),
	);
}

function mkt_measurement_can_manage() {
	return current_user_can( 'manage_options' );
}

function mkt_measurement_set_gtm_container( $input ) {
	if ( ! is_array( $input ) ) {
		return new WP_Error( 'invalid_input', __( 'Input must be an object.', 'mkt-measurement' ) );
	}
	if ( empty( $input['confirm'] ) ) {
		return new WP_Error( 'confirmation_required', __( 'confirm=true is required.', 'mkt-measurement' ) );
	}

	$container_id = isset( $input['gtm_container_id'] ) ? strtoupper( trim( (string) $input['gtm_container_id'] ) ) : '';
	if ( ! mkt_measurement_valid_gtm_id( $container_id ) ) {
		return new WP_Error( 'invalid_gtm_id', __( 'A valid GTM-XXXX container ID is required.', 'mkt-measurement' ) );
	}

	$enabled = ! empty( $input['enabled'] );
	update_option( MKT_MEASUREMENT_GTM_OPTION, $container_id, false );
	update_option( MKT_MEASUREMENT_GTM_ENABLED_OPTION, $enabled, false );

	return mkt_measurement_get_config();
}

function mkt_measurement_register_abilities() {
	if ( ! function_exists( 'wp_register_ability' ) ) {
		return;
	}

	$mcp_meta = array(
		'mcp' => array(
			'public' => true,
		),
	);

	wp_register_ability(
		'mkt-measurement/get-config',
		array(
			'label'               => __( 'Get measurement configuration', 'mkt-measurement' ),
			'description'         => __( 'Returns the GTM configuration managed by MKT Measurement Bridge.', 'mkt-measurement' ),
			'category'            => 'mkt-measurement',
			'output_schema'       => array(
				'type'       => 'object',
				'properties' => array(
					'gtm_container_id' => array( 'type' => 'string' ),
					'gtm_enabled'      => array( 'type' => 'boolean' ),
					'wordpress'        => array( 'type' => 'string' ),
					'home_url'         => array( 'type' => 'string' ),
				),
			),
			'execute_callback'     => 'mkt_measurement_get_config',
			'permission_callback'  => 'mkt_measurement_can_manage',
			'meta'                 => $mcp_meta,
		)
	);

	wp_register_ability(
		'mkt-measurement/set-gtm-container',
		array(
			'label'              => __( 'Set GTM container', 'mkt-measurement' ),
			'description'        => __( 'Configures GTM injection. Requires an administrator and confirm=true.', 'mkt-measurement' ),
			'category'           => 'mkt-measurement',
			'input_schema'       => array(
				'type'       => 'object',
				'required'   => array( 'gtm_container_id', 'confirm' ),
				'properties' => array(
					'gtm_container_id' => array(
						'type'    => 'string',
						'pattern' => '^GTM-[A-Za-z0-9]+$',
					),
					'enabled'          => array( 'type' => 'boolean' ),
					'confirm'          => array( 'type' => 'boolean' ),
				),
			),
			'output_schema'      => array( 'type' => 'object' ),
			'execute_callback'    => 'mkt_measurement_set_gtm_container',
			'permission_callback' => 'mkt_measurement_can_manage',
			'meta'                => $mcp_meta,
		)
	);
}
add_action( 'wp_abilities_api_init', 'mkt_measurement_register_abilities' );

function mkt_measurement_print_gtm_head() {
	if ( ! mkt_measurement_enabled() ) {
		return;
	}
	$container_id = mkt_measurement_container_id();
	if ( '' === $container_id ) {
		return;
	}
	?>
	<!-- Google Tag Manager: managed by MKT Measurement Bridge -->
	<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
	new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
	j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
	'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
	})(window,document,'script','dataLayer',<?php echo wp_json_encode( $container_id ); ?>);</script>
	<!-- End Google Tag Manager -->
	<?php
}
add_action( 'wp_head', 'mkt_measurement_print_gtm_head', 1 );

function mkt_measurement_print_gtm_body() {
	if ( ! mkt_measurement_enabled() ) {
		return;
	}
	$container_id = mkt_measurement_container_id();
	if ( '' === $container_id ) {
		return;
	}
	?>
	<!-- Google Tag Manager (noscript): managed by MKT Measurement Bridge -->
	<noscript><iframe src="<?php echo esc_url( 'https://www.googletagmanager.com/ns.html?id=' . rawurlencode( $container_id ) ); ?>"
	height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
	<!-- End Google Tag Manager (noscript) -->
	<?php
}
add_action( 'wp_body_open', 'mkt_measurement_print_gtm_body', 1 );
