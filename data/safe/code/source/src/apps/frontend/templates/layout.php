<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <title><?php echo $sf_response->getTitle() ?></title>
    <?php include_javascripts() ?>
</head>
<body>
    <div id="pasek-komunikatow"></div>
    <?php echo $sf_content ?>
</body>
</html>
