-- Rupia — esquema de negocio (personas + inventario + cuentas + unidades de negocio + ventas)
-- Usar con MySQL Workbench 8.0 CE (modelador EER), no con Workbench 26.x.
--
-- Workbench 8.0 (sin servidor MySQL):
--   File → New Model → File → Import → Reverse Engineer MySQL Create Script
--   Elegí este archivo, marcá "Place imported objects on a diagram" → Save Model (.mwb)

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE DATABASE IF NOT EXISTS `rupia`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE `rupia`;

CREATE TABLE IF NOT EXISTS `cuentas` (
  `cuen_id` int NOT NULL AUTO_INCREMENT,
  `cuen_descripcion` varchar(200) NOT NULL,
  `cuen_nombre_corto` varchar(20) NOT NULL,
  `cuen_es_banco` tinyint(1) NOT NULL DEFAULT 0,
  `cuen_es_tarjeta` tinyint(1) NOT NULL DEFAULT 0,
  `cuen_numero` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`cuen_id`),
  UNIQUE KEY `cuen_descripcion` (`cuen_descripcion`),
  UNIQUE KEY `cuen_nombre_corto` (`cuen_nombre_corto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `unidades_negocio` (
  `unidnego_id` int NOT NULL AUTO_INCREMENT,
  `unidnego_descripcion` varchar(200) NOT NULL,
  `unidnego_abreviado` varchar(20) NOT NULL,
  PRIMARY KEY (`unidnego_id`),
  UNIQUE KEY `unidnego_descripcion` (`unidnego_descripcion`),
  UNIQUE KEY `unidnego_abreviado` (`unidnego_abreviado`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `personas` (
  `pers_id` int NOT NULL AUTO_INCREMENT,
  `pers_tipo_documento` varchar(6) NOT NULL,
  `pers_documento` varchar(45) NOT NULL,
  `pers_razon_social` varchar(300) NOT NULL,
  `pers_fecha_nacimiento` date DEFAULT NULL,
  `pers_genero` varchar(11) NOT NULL,
  `pers_direccion` varchar(300) NOT NULL,
  `pers_celular` varchar(30) DEFAULT NULL,
  `pers_activo` tinyint(1) NOT NULL DEFAULT 1,
  `pers_observacion` varchar(300) DEFAULT NULL,
  `pers_es_cliente` tinyint(1) NOT NULL DEFAULT 0,
  `pers_es_proveedor` tinyint(1) NOT NULL DEFAULT 0,
  `pers_es_empleado` tinyint(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`pers_id`),
  UNIQUE KEY `pers_documento` (`pers_documento`),
  CONSTRAINT `personas_al_menos_un_rol` CHECK (
    (`pers_es_cliente` = 1) OR (`pers_es_proveedor` = 1) OR (`pers_es_empleado` = 1)
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `marcas` (
  `marc_id` int NOT NULL AUTO_INCREMENT,
  `marc_descripcion` varchar(200) NOT NULL,
  PRIMARY KEY (`marc_id`),
  UNIQUE KEY `marc_descripcion` (`marc_descripcion`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `items_categorias` (
  `itemcate_id` int NOT NULL AUTO_INCREMENT,
  `itemcate_descripcion` varchar(300) NOT NULL,
  PRIMARY KEY (`itemcate_id`),
  UNIQUE KEY `itemcate_descripcion` (`itemcate_descripcion`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `unidades_medidas` (
  `unidmedi_id` int NOT NULL AUTO_INCREMENT,
  `unidmedi_descripcion` varchar(100) NOT NULL,
  `unidmedi_simbolo` varchar(10) NOT NULL,
  PRIMARY KEY (`unidmedi_id`),
  UNIQUE KEY `unidmedi_descripcion` (`unidmedi_descripcion`),
  UNIQUE KEY `unidmedi_simbolo` (`unidmedi_simbolo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `items` (
  `item_id` int NOT NULL AUTO_INCREMENT,
  `item_marc_id` int NOT NULL,
  `item_itemcate_id` int NOT NULL,
  `item_unidmedi_id` int NOT NULL,
  `item_unidnego_id` int DEFAULT NULL,
  `item_codigo_barra` varchar(300) DEFAULT NULL,
  `item_descripcion` varchar(300) NOT NULL,
  `item_tipo` varchar(8) NOT NULL,
  `item_activo` tinyint(1) NOT NULL DEFAULT 1,
  `item_precio` decimal(15,3) DEFAULT NULL,
  `item_tasa_iva` smallint unsigned NOT NULL DEFAULT 10,
  `item_ultimo_costo` decimal(15,3) DEFAULT NULL,
  `item_precio_segun_costo` tinyint(1) NOT NULL DEFAULT 0,
  `item_imagen` varchar(200) DEFAULT NULL,
  PRIMARY KEY (`item_id`),
  UNIQUE KEY `item_descripcion` (`item_descripcion`),
  KEY `items_item_marc_id` (`item_marc_id`),
  KEY `items_item_itemcate_id` (`item_itemcate_id`),
  KEY `items_item_unidmedi_id` (`item_unidmedi_id`),
  KEY `items_item_unidnego_id` (`item_unidnego_id`),
  CONSTRAINT `items_item_marc_id_fk` FOREIGN KEY (`item_marc_id`)
    REFERENCES `marcas` (`marc_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `items_item_itemcate_id_fk` FOREIGN KEY (`item_itemcate_id`)
    REFERENCES `items_categorias` (`itemcate_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `items_item_unidmedi_id_fk` FOREIGN KEY (`item_unidmedi_id`)
    REFERENCES `unidades_medidas` (`unidmedi_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `items_item_unidnego_id_fk` FOREIGN KEY (`item_unidnego_id`)
    REFERENCES `unidades_negocio` (`unidnego_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ajustes_stock` (
  `ajusstoc_id` int unsigned NOT NULL,
  `ajusstoc_fecha` varchar(45) NOT NULL,
  `ajusstoc_observacion` varchar(45) NOT NULL,
  PRIMARY KEY (`ajusstoc_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `items_movimientos` (
  `itemmovi_id` int NOT NULL,
  `itemmovi_item_id` int NOT NULL,
  `itemmovi_unidmedi_id` int NOT NULL,
  `itemmovi_tipo` varchar(2) NOT NULL,
  `itemmovi_fecha_movimiento` date NOT NULL,
  `itemmovi_cantidad` decimal(15,3) NOT NULL,
  `itemmovi_precio` decimal(15,3) NOT NULL,
  `itemmovi_costo` decimal(15,3) NOT NULL,
  `itemmovi_subtotal` decimal(15,3) NOT NULL,
  `itemmovi_secuencia_origen` varchar(45) DEFAULT NULL,
  `itemmovi_secuencia_detalle_origen` int DEFAULT NULL,
  `itemmovi_es_vigente` tinyint(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`itemmovi_id`),
  KEY `items_movimientos_itemmovi_item_id` (`itemmovi_item_id`),
  KEY `items_movimientos_itemmovi_unidmedi_id` (`itemmovi_unidmedi_id`),
  CONSTRAINT `items_movimientos_itemmovi_item_id_fk` FOREIGN KEY (`itemmovi_item_id`)
    REFERENCES `items` (`item_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `items_movimientos_itemmovi_unidmedi_id_fk` FOREIGN KEY (`itemmovi_unidmedi_id`)
    REFERENCES `unidades_medidas` (`unidmedi_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ajustes_stock_detalles` (
  `ajusstocdeta_id` int unsigned NOT NULL,
  `ajusstocdeta_ajusstoc_id` int unsigned NOT NULL,
  `ajusstocdeta_item_id` int NOT NULL,
  `ajusstocdeta_unidmedi_id` int NOT NULL,
  `ajusstocdeta_cantidad_anterior` decimal(15,3) NOT NULL,
  `ajusstocdeta_cantidad_nueva` decimal(15,3) NOT NULL,
  `ajusstocdeta_cantidad` decimal(15,3) NOT NULL,
  PRIMARY KEY (`ajusstocdeta_id`),
  KEY `ajustes_stock_detalles_ajusstoc_id` (`ajusstocdeta_ajusstoc_id`),
  KEY `ajustes_stock_detalles_item_id` (`ajusstocdeta_item_id`),
  KEY `ajustes_stock_detalles_unidmedi_id` (`ajusstocdeta_unidmedi_id`),
  CONSTRAINT `ajustes_stock_detalles_ajusstoc_id_fk` FOREIGN KEY (`ajusstocdeta_ajusstoc_id`)
    REFERENCES `ajustes_stock` (`ajusstoc_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ajustes_stock_detalles_item_id_fk` FOREIGN KEY (`ajusstocdeta_item_id`)
    REFERENCES `items` (`item_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ajustes_stock_detalles_unidmedi_id_fk` FOREIGN KEY (`ajusstocdeta_unidmedi_id`)
    REFERENCES `unidades_medidas` (`unidmedi_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `items_precios_historial` (
  `itprehist_id` int NOT NULL AUTO_INCREMENT,
  `itprehist_item_id` int NOT NULL,
  `itprehist_precio_anterior` decimal(15,3) DEFAULT NULL,
  `itprehist_precio_nuevo` decimal(15,3) DEFAULT NULL,
  `itprehist_ultimo_costo` decimal(15,3) DEFAULT NULL,
  `itprehist_porcentaje` decimal(6,2) DEFAULT NULL,
  `itprehist_segun_costo` tinyint(1) NOT NULL,
  `itprehist_origen` varchar(6) NOT NULL,
  `itprehist_usuario_id` int NOT NULL,
  `itprehist_fecha` datetime NOT NULL,
  `itprehist_lote` char(32) DEFAULT NULL,
  PRIMARY KEY (`itprehist_id`),
  KEY `items_precios_historial_item_id` (`itprehist_item_id`),
  KEY `items_precios_historial_usuario_id` (`itprehist_usuario_id`),
  KEY `items_precios_historial_fecha` (`itprehist_fecha`),
  KEY `items_precios_historial_lote` (`itprehist_lote`),
  CONSTRAINT `items_precios_historial_item_id_fk` FOREIGN KEY (`itprehist_item_id`)
    REFERENCES `items` (`item_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `items_unidades` (
  `itemunid_id` int NOT NULL AUTO_INCREMENT,
  `itemunid_item_id` int NOT NULL,
  `itemunid_unidmedi_id` int NOT NULL,
  `itemunid_relacion` varchar(5) NOT NULL,
  `itemunid_valor` decimal(15,3) NOT NULL,
  PRIMARY KEY (`itemunid_id`),
  UNIQUE KEY `items_unidades_item_unidad` (`itemunid_item_id`, `itemunid_unidmedi_id`),
  KEY `items_unidades_unidmedi_id` (`itemunid_unidmedi_id`),
  CONSTRAINT `items_unidades_item_id_fk` FOREIGN KEY (`itemunid_item_id`)
    REFERENCES `items` (`item_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `items_unidades_unidmedi_id_fk` FOREIGN KEY (`itemunid_unidmedi_id`)
    REFERENCES `unidades_medidas` (`unidmedi_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `puntos_expedicion` (
  `puntexpe_id` int NOT NULL AUTO_INCREMENT,
  `puntexpe_tipo` varchar(8) NOT NULL,
  `puntexpe_establecimiento` varchar(3) NOT NULL,
  `puntexpe_codigo` varchar(3) NOT NULL,
  `puntexpe_timbrado` varchar(20) NOT NULL,
  `puntexpe_vigencia_desde` date NOT NULL,
  `puntexpe_vigencia_hasta` date NOT NULL,
  `puntexpe_numero_desde` int unsigned NOT NULL,
  `puntexpe_numero_hasta` int unsigned NOT NULL,
  `puntexpe_numero_proximo` int unsigned NOT NULL,
  `puntexpe_emisor_razon_social` varchar(300) NOT NULL,
  `puntexpe_emisor_ruc` varchar(45) NOT NULL,
  `puntexpe_emisor_direccion` varchar(300) NOT NULL,
  `puntexpe_emisor_telefono` varchar(45) NOT NULL DEFAULT '',
  `puntexpe_emisor_actividad` varchar(300) NOT NULL DEFAULT '',
  PRIMARY KEY (`puntexpe_id`),
  UNIQUE KEY `puntexpe_tipo` (`puntexpe_tipo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ventas` (
  `vent_id` int NOT NULL AUTO_INCREMENT,
  `vent_fecha` date NOT NULL,
  `vent_estado` varchar(8) NOT NULL,
  `vent_pers_id` int DEFAULT NULL,
  `vent_caja_id` int DEFAULT NULL,
  `vent_cuen_id` int DEFAULT NULL,
  `vent_medio` varchar(14) NOT NULL,
  `vent_descuento` decimal(15,3) NOT NULL DEFAULT 0,
  `vent_importe_recibido` decimal(15,3) NOT NULL DEFAULT 0,
  `vent_observacion` varchar(300) NOT NULL DEFAULT '',
  `vent_usuario_id` int NOT NULL,
  `vent_tipo_comprobante` varchar(8) NOT NULL,
  `vent_puntexpe_id` int DEFAULT NULL,
  `vent_timbrado` varchar(20) NOT NULL DEFAULT '',
  `vent_vigencia_desde` date DEFAULT NULL,
  `vent_vigencia_hasta` date DEFAULT NULL,
  `vent_establecimiento` varchar(3) NOT NULL DEFAULT '',
  `vent_punto_codigo` varchar(3) NOT NULL DEFAULT '',
  `vent_secuencial` int unsigned DEFAULT NULL,
  `vent_numero_completo` varchar(15) DEFAULT NULL,
  `vent_emisor_razon_social` varchar(300) NOT NULL DEFAULT '',
  `vent_emisor_ruc` varchar(45) NOT NULL DEFAULT '',
  `vent_emisor_direccion` varchar(300) NOT NULL DEFAULT '',
  `vent_emisor_telefono` varchar(45) NOT NULL DEFAULT '',
  `vent_emisor_actividad` varchar(300) NOT NULL DEFAULT '',
  `vent_condicion` varchar(8) NOT NULL,
  PRIMARY KEY (`vent_id`),
  UNIQUE KEY `ventas_numero_completo` (`vent_numero_completo`),
  KEY `ventas_pers_id` (`vent_pers_id`),
  KEY `ventas_caja_id` (`vent_caja_id`),
  KEY `ventas_cuen_id` (`vent_cuen_id`),
  KEY `ventas_usuario_id` (`vent_usuario_id`),
  KEY `ventas_puntexpe_id` (`vent_puntexpe_id`),
  CONSTRAINT `ventas_pers_id_fk` FOREIGN KEY (`vent_pers_id`)
    REFERENCES `personas` (`pers_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ventas_caja_id_fk` FOREIGN KEY (`vent_caja_id`)
    REFERENCES `cuentas` (`cuen_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ventas_cuen_id_fk` FOREIGN KEY (`vent_cuen_id`)
    REFERENCES `cuentas` (`cuen_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ventas_puntexpe_id_fk` FOREIGN KEY (`vent_puntexpe_id`)
    REFERENCES `puntos_expedicion` (`puntexpe_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ventas_detalles` (
  `ventdeta_id` int NOT NULL AUTO_INCREMENT,
  `ventdeta_vent_id` int NOT NULL,
  `ventdeta_item_id` int NOT NULL,
  `ventdeta_unidmedi_id` int NOT NULL,
  `ventdeta_cantidad` decimal(15,3) NOT NULL,
  `ventdeta_precio` decimal(15,3) NOT NULL,
  `ventdeta_tasa_iva` smallint unsigned NOT NULL,
  `ventdeta_subtotal` decimal(15,3) NOT NULL,
  PRIMARY KEY (`ventdeta_id`),
  KEY `ventas_detalles_vent_id` (`ventdeta_vent_id`),
  KEY `ventas_detalles_item_id` (`ventdeta_item_id`),
  KEY `ventas_detalles_unidmedi_id` (`ventdeta_unidmedi_id`),
  CONSTRAINT `ventas_detalles_vent_id_fk` FOREIGN KEY (`ventdeta_vent_id`)
    REFERENCES `ventas` (`vent_id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `ventas_detalles_item_id_fk` FOREIGN KEY (`ventdeta_item_id`)
    REFERENCES `items` (`item_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ventas_detalles_unidmedi_id_fk` FOREIGN KEY (`ventdeta_unidmedi_id`)
    REFERENCES `unidades_medidas` (`unidmedi_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
