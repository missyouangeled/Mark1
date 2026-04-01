<?php
require __DIR__ . '/config.php';
start_session_if_needed();
session_unset();
session_destroy();
redirect_to('/');
