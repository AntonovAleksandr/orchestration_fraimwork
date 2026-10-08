---
name: develop-gloriaots-database
version: 1.0.0
layer: stack
platform: Gloria OTS
compatibility: ">=1.0.0,<2.0.0"
deprecated: false
reusable: true
---


# Develop Gloria OTS Database Layer

Управление SQL Server БД для Gloria OTS (Database/SqlDeploy).

## Database Architecture

```
Database/
├── SqlDeploy/
│   ├── v202601_initial_schema.sql     # Initial schema
│   ├── v202602_add_shipment_tables.sql
│   ├── v202609_add_dpd_carrier.sql
│   └── ...
├── Scripts/
│   ├── init-db.sql                    # One-time setup
│   └── seed-reference-data.sql
└── Diagrams/
    └── ER-diagram.md
```

**Principes:**
- Manual (no auto-migrations on startup)
- One SQL file per logical change
- Idempotent (safe to re-run)
- Versioning: `vYYYYMM##_description.sql`
- Tracked in git

## Schema Design

### Core Tables

```sql
-- Orders table
CREATE TABLE [Orders] (
  [OrderId] INT PRIMARY KEY IDENTITY(1,1),
  [OrderNumber] NVARCHAR(50) NOT NULL UNIQUE,
  [CustomerId] INT NOT NULL,
  [Status] NVARCHAR(50) NOT NULL,  -- PENDING, SHIPPED, DELIVERED, CANCELLED
  [ShipmentService] INT NOT NULL,  -- foreign key to enum
  [TrackingNumber] NVARCHAR(255) NULL,
  [CreatedAt] DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
  [UpdatedAt] DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
  [ShippedAt] DATETIME2 NULL,
  [DeliveredAt] DATETIME2 NULL,
  [CancelledAt] DATETIME2 NULL,
  CONSTRAINT FK_Orders_ShipmentService FOREIGN KEY ([ShipmentService])
    REFERENCES [ShipmentServices]([Id])
);

CREATE INDEX IDX_Orders_Status ON [Orders]([Status]) WHERE [Status] != 'DELIVERED';
CREATE INDEX IDX_Orders_TrackingNumber ON [Orders]([TrackingNumber]) WHERE [TrackingNumber] IS NOT NULL;
CREATE INDEX IDX_Orders_CreatedAt ON [Orders]([CreatedAt]);

-- Shipments table
CREATE TABLE [Shipments] (
  [ShipmentId] INT PRIMARY KEY IDENTITY(1,1),
  [OrderId] INT NOT NULL,
  [TrackingNumber] NVARCHAR(255) NOT NULL UNIQUE,
  [CarrierId] INT NOT NULL,
  [Status] NVARCHAR(50) NOT NULL,
  [LastStatusUpdate] DATETIME2 NULL,
  [EstimatedDelivery] DATETIME2 NULL,
  [ActualDelivery] DATETIME2 NULL,
  CONSTRAINT FK_Shipments_Order FOREIGN KEY ([OrderId])
    REFERENCES [Orders]([OrderId]) ON DELETE CASCADE
);

CREATE INDEX IDX_Shipments_TrackingNumber ON [Shipments]([TrackingNumber]);
CREATE INDEX IDX_Shipments_CarrierId ON [Shipments]([CarrierId]);

-- Reference data: Shipment services
CREATE TABLE [ShipmentServices] (
  [Id] INT PRIMARY KEY,
  [Code] NVARCHAR(50) NOT NULL UNIQUE,  -- DPD, CDEK, RPOST
  [Name] NVARCHAR(255) NOT NULL,
  [IsActive] BIT NOT NULL DEFAULT 1
);

-- Reference data: initial carriers
INSERT INTO [ShipmentServices] ([Id], [Code], [Name])
VALUES
  (1, 'DPD', 'DPD Express'),
  (2, 'CDEK', 'CDEK'),
  (3, 'RPOST', 'Russian Post');
```

## Migration File Patterns

### Adding a New Carrier (v202609_add_dpd_carrier.sql)

```sql
-- ==============================================
-- Migration: Add DPD Carrier Support
-- Version: v202609_add_dpd_carrier
-- Author: Claude Haiku
-- Date: 2026-09-02
-- Description: Add DPD shipment service and related columns
-- ==============================================

-- Step 1: Add DPD to reference data (if not exists)
IF NOT EXISTS (SELECT 1 FROM [ShipmentServices] WHERE [Code] = 'DPD')
BEGIN
  INSERT INTO [ShipmentServices] ([Id], [Code], [Name], [IsActive])
  VALUES (1, 'DPD', 'DPD Express', 1);
  
  PRINT 'DPD service added to [ShipmentServices]';
END
GO

-- Step 2: Add DPD-specific columns to Shipments (if not exists)
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS 
  WHERE TABLE_NAME = 'Shipments' AND COLUMN_NAME = 'DpdTrackingUrl')
BEGIN
  ALTER TABLE [Shipments]
  ADD [DpdTrackingUrl] NVARCHAR(1000) NULL,
      [DpdPickupDate] DATETIME2 NULL,
      [DpdLastUpdateAt] DATETIME2 NULL;
  
  PRINT 'DPD columns added to [Shipments] table';
END
GO

-- Step 3: Create index for DPD tracking lookups
IF NOT EXISTS (
  SELECT 1 FROM sys.indexes 
  WHERE name = 'IDX_Shipments_DpdTracking' AND object_id = OBJECT_ID('[Shipments]')
)
BEGIN
  CREATE INDEX [IDX_Shipments_DpdTracking] ON [Shipments]([DpdTrackingUrl]) 
  WHERE [DpdTrackingUrl] IS NOT NULL;
  
  PRINT 'Index IDX_Shipments_DpdTracking created';
END
GO

-- Step 4: Verify migration (optional)
SELECT COUNT(*) as [DpdShipmentCount] FROM [ShipmentServices] WHERE [Code] = 'DPD';
SELECT COUNT(*) as [ShipmentsWithDpd] FROM [Shipments] WHERE [DpdTrackingUrl] IS NOT NULL;
GO

-- Migration complete
PRINT 'Migration v202609_add_dpd_carrier completed successfully';
```

### Key Patterns

✅ **ПРАВИЛЬНО:**
- `IF NOT EXISTS (...)` checks (idempotent)
- `ALTER TABLE ... ADD` only if column not exists
- `CREATE INDEX IF NOT EXISTS` patterns
- `PRINT` statements for logging
- Single responsibility (one logical change per file)
- Comments explaining the why (not what)

❌ **ПЛОХО:**
- Direct `ALTER TABLE` without existence check (fails on re-run)
- `DROP TABLE` without `IF EXISTS`
- No comments or documentation
- Multiple unrelated changes in one file
- Hardcoded values instead of reference data

## Stored Procedures

### Get Order with Shipments (Read)

```sql
CREATE PROCEDURE sp_GetOrderWithShipments
  @OrderId INT
AS
BEGIN
  SET NOCOUNT ON;
  
  SELECT 
    o.[OrderId],
    o.[OrderNumber],
    o.[Status],
    o.[TrackingNumber],
    o.[CreatedAt],
    s.[ShipmentId],
    s.[TrackingNumber] as [ShipmentTrackingNumber],
    s.[Status] as [ShipmentStatus],
    s.[EstimatedDelivery]
  FROM [Orders] o
  LEFT JOIN [Shipments] s ON o.[OrderId] = s.[OrderId]
  WHERE o.[OrderId] = @OrderId;
END
GO
```

### Update Order Status (Write)

```sql
CREATE PROCEDURE sp_UpdateOrderStatus
  @OrderId INT,
  @NewStatus NVARCHAR(50),
  @UpdatedBy NVARCHAR(100)
AS
BEGIN
  SET NOCOUNT ON;
  BEGIN TRANSACTION;
  
  BEGIN TRY
    -- Validate order exists
    IF NOT EXISTS (SELECT 1 FROM [Orders] WHERE [OrderId] = @OrderId)
    BEGIN
      THROW 50404, 'Order not found', 1;
    END
    
    -- Validate status transition
    DECLARE @CurrentStatus NVARCHAR(50);
    SELECT @CurrentStatus = [Status] FROM [Orders] WHERE [OrderId] = @OrderId;
    
    -- Only allow forward transitions (simplified)
    IF @CurrentStatus = 'CANCELLED'
    BEGIN
      THROW 50400, 'Cannot update cancelled order', 1;
    END
    
    -- Update order
    UPDATE [Orders]
    SET 
      [Status] = @NewStatus,
      [UpdatedAt] = GETUTCDATE()
    WHERE [OrderId] = @OrderId;
    
    -- Log audit trail (if audit table exists)
    IF OBJECT_ID('OrderAudit') IS NOT NULL
    BEGIN
      INSERT INTO [OrderAudit] ([OrderId], [OldStatus], [NewStatus], [ChangedBy], [ChangedAt])
      VALUES (@OrderId, @CurrentStatus, @NewStatus, @UpdatedBy, GETUTCDATE());
    END
    
    COMMIT TRANSACTION;
  END TRY
  BEGIN CATCH
    IF @@TRANCOUNT > 0
      ROLLBACK TRANSACTION;
    
    THROW;
  END CATCH
END
GO
```

## Data Seeding

### Reference Data Seed (seed-reference-data.sql)

```sql
-- Shipment services reference data
MERGE INTO [ShipmentServices] AS target
USING (VALUES
  (1, 'DPD', 'DPD Express'),
  (2, 'CDEK', 'CDEK'),
  (3, 'RPOST', 'Russian Post')
) AS source (Id, Code, Name)
ON target.Id = source.Id
WHEN MATCHED AND target.Name <> source.Name THEN
  UPDATE SET Name = source.Name
WHEN NOT MATCHED THEN
  INSERT ([Id], [Code], [Name], [IsActive])
  VALUES (source.Id, source.Code, source.Name, 1);

-- Order statuses
MERGE INTO [OrderStatuses] AS target
USING (VALUES
  (1, 'PENDING', 'Pending'),
  (2, 'SHIPPED', 'Shipped'),
  (3, 'DELIVERED', 'Delivered'),
  (4, 'CANCELLED', 'Cancelled')
) AS source (Id, Code, Name)
ON target.Id = source.Id
WHEN NOT MATCHED THEN
  INSERT ([Id], [Code], [Name])
  VALUES (source.Id, source.Code, source.Name);
```

## Deployment & Versioning

### SqlDeploy Execution

```bash
# One-time database setup
sqlcmd -S localhost -d gloria_ots -i Database/Scripts/init-db.sql

# Apply all pending migrations (in order)
for file in Database/SqlDeploy/v*.sql; do
  echo "Applying $file..."
  sqlcmd -S localhost -d gloria_ots -i "$file"
  if [ $? -ne 0 ]; then
    echo "Migration failed!"
    exit 1
  fi
done
```

### Version Tracking Table

```sql
-- Track applied migrations
CREATE TABLE [__MigrationHistory] (
  [MigrationId] NVARCHAR(255) PRIMARY KEY,
  [AppliedAt] DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
  [AppliedBy] NVARCHAR(100),
  [ExecutionTimeMs] INT
);

-- Before applying migration, check if already applied
IF NOT EXISTS (SELECT 1 FROM [__MigrationHistory] WHERE [MigrationId] = 'v202609_add_dpd_carrier')
BEGIN
  -- ... apply migration ...
  
  INSERT INTO [__MigrationHistory] ([MigrationId], [AppliedBy], [ExecutionTimeMs])
  VALUES ('v202609_add_dpd_carrier', USER_NAME(), 1234);
END
```

## Backup & Rollback

### Backup Before Major Changes

```sql
-- Before running critical migration, backup current schema
BACKUP DATABASE [gloria_ots]
TO DISK = N'C:\Backups\gloria_ots_pre_migration_20260902.bak'
WITH INIT, COMPRESSION, STATS = 10;

-- Verify backup
RESTORE HEADERONLY FROM DISK = N'C:\Backups\gloria_ots_pre_migration_20260902.bak';
```

### Rollback Pattern

```sql
-- Rollback migration v202609_add_dpd_carrier
-- (Keep this in same file for easy rollback)

-- ROLLBACK: Remove DPD columns from Shipments
IF EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS 
  WHERE TABLE_NAME = 'Shipments' AND COLUMN_NAME = 'DpdTrackingUrl')
BEGIN
  ALTER TABLE [Shipments] DROP COLUMN [DpdTrackingUrl];
  ALTER TABLE [Shipments] DROP COLUMN [DpdPickupDate];
  ALTER TABLE [Shipments] DROP COLUMN [DpdLastUpdateAt];
END
GO

-- ROLLBACK: Remove DPD from reference data (optional - might keep reference)
-- DELETE FROM [ShipmentServices] WHERE [Code] = 'DPD';

PRINT 'Rollback of v202609_add_dpd_carrier completed';
```

## Query Performance

### Execution Plans

```sql
-- Enable actual execution plan
SET STATISTICS IO ON;
SET STATISTICS TIME ON;

-- Query to analyze
SELECT o.OrderId, o.OrderNumber, s.TrackingNumber, s.Status
FROM [Orders] o
LEFT JOIN [Shipments] s ON o.OrderId = s.OrderId
WHERE o.Status = 'SHIPPED' AND o.CreatedAt > DATEADD(DAY, -7, GETUTCDATE());

-- Check results (look for table scans → create index)
SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
```

### Index Strategy

```sql
-- Non-clustered index for frequent WHERE clauses
CREATE INDEX IDX_Orders_Status_CreatedAt ON [Orders]([Status], [CreatedAt])
WHERE [Status] <> 'DELIVERED';  -- filtered index for active orders only

-- Index on foreign key relationships
CREATE INDEX IDX_Shipments_OrderId ON [Shipments]([OrderId]);
```

## Documentation

### Schema Diagram

```markdown
# Gloria OTS Schema

## Orders
- PK: OrderId
- FK: ShipmentServiceId → ShipmentServices
- Status: PENDING | SHIPPED | DELIVERED | CANCELLED
- Indexes: Status, TrackingNumber, CreatedAt

## Shipments
- PK: ShipmentId
- FK: OrderId → Orders (CASCADE)
- FK: CarrierId (reference to carrier config)
- Status: tracking statuses (carrier-specific)
```

## Testing Migrations

```csharp
[IntegrationTest]
public async Task Migration_AddDpdCarrier_CreatesTableAndData()
{
  // Arrange
  var dbContext = new OrdersDbContext(_dbContextOptions);
  
  // Act
  await dbContext.Database.MigrateAsync();
  
  // Assert
  var dpdService = await dbContext.ShipmentServices
    .FirstOrDefaultAsync(s => s.Code == "DPD");
  
  Assert.NotNull(dpdService);
  Assert.Equal("DPD Express", dpdService.Name);
}
```

## Related Skills

- **pattern-development-gloriaots** — full 7-step workflow
- **gloriaots-stack-anatomy** — architecture overview
- **develop-gloriaots-infrastructure** — EF Core usage
- **gloriaots-gitlab-mr-review** — review checklist

---

**Version:** 1.0  
**Platform:** Gloria OTS (SQL Server)  
**Last Updated:** 2026-10-06
