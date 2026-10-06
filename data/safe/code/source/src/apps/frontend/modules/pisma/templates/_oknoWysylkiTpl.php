<div class="okno-wysylki">
    <p>Kanał wysyłki: <strong><?php echo $pismo->kanal_wysylki ?></strong></p>
    <p>Status: <span id="status-wysylki"><?php echo $pismo->status_wysylki ?></span></p>
    <button data-akcja="pisma/zapisz" data-id="<?php echo $pismo->id ?>">Zapisz</button>
    <button data-akcja="pisma/wyslij" data-id="<?php echo $pismo->id ?>">Wyślij</button>
</div>
